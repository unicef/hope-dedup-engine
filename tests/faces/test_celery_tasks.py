import json
from unittest.mock import MagicMock, patch

import pytest

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.security.models import System
from hope_dedup_engine.apps.faces.celery_tasks import (
    callback_encodings,
    callback_findings,
    dedupe_chunk,
    deduplicate_dataset,
)


@pytest.fixture
def mock_redis(mocker):
    """Mock get_redis_connection to return a MagicMock."""
    mock_redis_conn = MagicMock()
    mocker.patch(
        "hope_dedup_engine.apps.faces.celery_tasks.get_redis_connection",
        return_value=mock_redis_conn,
    )
    return mock_redis_conn


@pytest.fixture
def deduplication_set(db):
    """Fixture to create a DeduplicationSet with a system."""
    system, _ = System.objects.get_or_create(name="default")
    return DeduplicationSet.objects.create(system=system)


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.deduplicate_dataset.delay")
def test_callback_encodings(mock_deduplicate_delay, mock_redis, mocker, deduplication_set):
    """Test that callback_encodings correctly caches data in Redis and starts the next phase."""
    mocker.patch("hope_dedup_engine.apps.faces.celery_tasks.TARGET_CHUNKS", 1)
    mocker.patch.object(
        DeduplicationSet,
        "get_encodings",
        return_value={"file1.jpg": [1.0], "file2.jpg": [2.0], "file3.jpg": [3.0]},
    )
    mocker.patch.object(DeduplicationSet, "get_ignored_pairs", return_value=[("pk1", "pk2")])

    newly_encoded_files = ["file1.jpg", "file2.jpg"]
    results = [newly_encoded_files]
    config = {"deduplication_set_id": str(deduplication_set.pk)}

    callback_encodings(results, config)

    assert mock_redis.set.call_count == 3  # ignored_pairs, new_chunk, existing_chunk

    dedup_prefix = f"hde:dedup:{deduplication_set.pk}"
    ignored_pairs_key = f"{dedup_prefix}:ignored_pairs"
    new_chunk_key = f"{dedup_prefix}:chunk:new:0"
    existing_chunk_key = f"{dedup_prefix}:chunk:existing:0"

    mock_redis.set.assert_any_call(ignored_pairs_key, json.dumps([("pk1", "pk2")]), ex=86400)
    mock_redis.set.assert_any_call(new_chunk_key, json.dumps({"file1.jpg": [1.0], "file2.jpg": [2.0]}), ex=86400)
    mock_redis.set.assert_any_call(existing_chunk_key, json.dumps({"file3.jpg": [3.0]}), ex=86400)

    mock_deduplicate_delay.assert_called_once()
    call_args = mock_deduplicate_delay.call_args.kwargs
    assert call_args["config"] == config
    assert call_args["new_chunk_keys"] == [new_chunk_key]
    assert call_args["existing_chunk_keys"] == [existing_chunk_key]
    assert call_args["ignored_pairs_key"] == ignored_pairs_key


@pytest.mark.django_db
def test_dedupe_chunk(mock_redis, deduplication_set):
    """Test that dedupe_chunk correctly deserializes data from Redis and calls dedupe_images."""
    config = {
        "deduplication_set_id": deduplication_set.pk,
        "deduplicate": {"threshold": 0.8},
    }
    chunk_key1, chunk_key2, ignored_pairs_key = "key1", "key2", "ignored"

    encodings1 = {"file1.jpg": [1.0, 0.0], "file2.jpg": [0.9, 0.1]}
    encodings2 = {"file3.jpg": [0.0, 1.0], "file4.jpg": [0.8, 0.2]}
    ignored_pairs = [("file1.jpg", "file4.jpg")]

    mock_redis.get.side_effect = [
        json.dumps(encodings1),
        json.dumps(encodings2),
        json.dumps(ignored_pairs),
    ]

    with patch("hope_dedup_engine.apps.faces.celery_tasks.dedupe_images") as mock_dedupe_images:
        mock_dedupe_images.return_value = "FINDINGS_RESULT"

        result = dedupe_chunk(chunk_key1, chunk_key2, ignored_pairs_key, config)

        assert result == "FINDINGS_RESULT"
        mock_dedupe_images.assert_called_once()
        args, kwargs = mock_dedupe_images.call_args
        assert args[0] == encodings1
        assert args[1] == encodings2
        assert args[2] == {("file1.jpg", "file4.jpg")}
        assert kwargs["dedupe_threshold"] == 0.8


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.chord")
@patch("hope_dedup_engine.apps.faces.celery_tasks.dedupe_chunk")
@patch("hope_dedup_engine.apps.faces.celery_tasks.callback_findings")
def test_deduplicate_dataset(mock_callback, mock_dedupe, mock_chord, deduplication_set):
    """Test that deduplicate_dataset constructs the correct chord of dedupe tasks."""
    config = {"deduplication_set_id": str(deduplication_set.pk)}
    new_keys = ["new1", "new2"]
    existing_keys = ["old1"]
    ignored_key = "ignored"
    deduplicate_dataset(config, new_keys, existing_keys, ignored_key)

    assert mock_dedupe.s.call_count == 5

    mock_chord.assert_called_once()
    tasks_arg = mock_chord.call_args[0][0]
    assert len(tasks_arg) == 5

    chord_callback = mock_chord.return_value
    chord_callback.assert_called_once_with(mock_callback.s.return_value)

    context = {"keys_to_delete": new_keys + existing_keys + [ignored_key]}
    mock_callback.s.assert_called_once_with(context=context, config=config)


@pytest.mark.django_db
def test_callback_findings(mock_redis, deduplication_set):
    """Test that callback_findings aggregates results, saves them, and cleans up Redis."""
    config = {"deduplication_set_id": str(deduplication_set.pk)}
    keys_to_delete = ["key1", "key2", "ignored"]
    context = {"keys_to_delete": keys_to_delete}

    results = [
        [("file1.jpg", "file2.jpg", 0.9, 200)],
        [("file3.jpg", "file4.jpg", 0.85, 200)],
        [("file2.jpg", "file1.jpg", 0.9, 200)],  # Duplicate pair
    ]

    with patch.object(DeduplicationSet, "update_findings") as mock_update_findings:
        callback_findings(results, context, config)

        mock_update_findings.assert_called_once()
        saved_findings = mock_update_findings.call_args[0][0]
        assert len(saved_findings) == 2
        assert ("file1.jpg", "file2.jpg", 0.9, 200) in saved_findings
        assert ("file3.jpg", "file4.jpg", 0.85, 200) in saved_findings

        mock_redis.delete.assert_called_once_with(*keys_to_delete)
