import json
from unittest.mock import ANY, Mock, patch

import pytest
from celery import states
from celery.canvas import Signature

from hope_dedup_engine.apps.api.models import DedupJob, DeduplicationSet
from hope_dedup_engine.apps.security.models import System
from hope_dedup_engine.apps.faces.celery_tasks import (
    callback_encodings,
    callback_findings,
    dedupe_chunk,
    deduplicate_dataset,
    encode_chunk,
    get_chunks,
    shadow_name,
    sync_dnn_files,
)
from testutils.factories.api import ImageFactory


@pytest.fixture
def dedup_set_with_job(db):
    """Fixture to create a DeduplicationSet with an associated DedupJob."""
    system, _ = System.objects.get_or_create(name="default")
    ds = DeduplicationSet.objects.create(name="test_set", system=system)
    DedupJob.objects.create(deduplication_set=ds, progress=0)
    return ds


@pytest.fixture
def mock_task():
    """Fixture to create a mock Celery task instance."""
    task = Mock()
    task.request.id = "task-id-123"
    task.update_state = Mock()
    return task


def test_get_chunks_balances(monkeypatch):
    monkeypatch.setattr("hope_dedup_engine.apps.faces.celery_tasks.TARGET_CHUNKS", 3)
    filenames = [f"f{i}" for i in range(10)]

    chunks = get_chunks(filenames)

    assert len(chunks) == min(len(filenames), 3)
    [len(chunk) for chunk in chunks]
    expected_chunk_size = (len(filenames) + len(chunks) - 1) // len(chunks)
    assert all(len(chunk) == expected_chunk_size for chunk in chunks[:-1])
    assert len(chunks[-1]) <= expected_chunk_size
    flattened = [item for chunk in chunks for item in chunk]
    assert set(flattened) == set(filenames)


def test_get_chunks_empty():
    assert get_chunks([]) == []


def test_shadow_name_success(mocker):
    """Test shadow_name generates the correct name for a task in a chord."""
    mocker.patch(
        "hope_dedup_engine.apps.faces.celery_tasks.qualname",
        return_value="test_task_qualname",
    )
    sig = Signature(task="test_task")
    type(sig).type = mocker.PropertyMock(return_value="mocked_task_type")
    options = {
        "chord": sig,
        "group_id": "some-group-id-abcde",
        "group_index": 1,
    }
    result = shadow_name(Mock(), [], {}, options)
    assert result == "test_task_qualname(abcde)-001"


def test_shadow_name_error(mocker):
    """Test shadow_name handles errors gracefully and reports to Sentry."""
    mock_capture = mocker.patch("sentry_sdk.capture_exception")
    result = shadow_name(Mock(), [], {}, {"chord": None})  # Trigger TypeError
    assert isinstance(result, str)
    mock_capture.assert_called_once()


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.encode_faces")
@patch("hope_dedup_engine.apps.faces.celery_tasks.notify_status")
def test_encode_chunk_success(mock_notify, mock_encode_faces, mock_get_ds, dedup_set_with_job, mocker):
    """Test encode_chunk successfully encodes faces and updates the dataset."""
    ds = dedup_set_with_job
    mock_get_ds.return_value = ds
    mocker.patch.object(ds, "get_encodings", return_value={})
    mocker.patch.object(ds, "update_encodings")

    def encode_side_effect(*args, **kwargs):
        kwargs["progress"]()
        return {"file1.jpg": [1.0]}, ["file1.jpg"], None

    mock_encode_faces.side_effect = encode_side_effect

    encode_chunk.run(["file1.jpg"], {"deduplication_set_id": ds.pk, "encoding": {}})

    mock_encode_faces.assert_called_once()
    ds.update_encodings.assert_called_once_with({"file1.jpg": [1.0]})
    mock_notify.assert_called()


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.encode_faces", side_effect=Exception("mock error"))
@patch("hope_dedup_engine.apps.faces.celery_tasks.sentry_sdk")
def test_encode_chunk_error(mock_sentry, mock_encode_faces, dedup_set_with_job):
    """Test encode_chunk handles exceptions correctly."""
    ds = dedup_set_with_job
    with pytest.raises(Exception, match="mock error"):
        encode_chunk.run(["file1.jpg"], {"deduplication_set_id": ds.pk})
    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.FAILED
    mock_sentry.capture_exception.assert_called_once()


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.get_redis_connection")
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.dedupe_images")
@patch("hope_dedup_engine.apps.faces.celery_tasks.notify_status")
def test_dedupe_chunk_success(mock_notify, mock_dedupe_images, mock_get_ds, mock_get_redis, dedup_set_with_job):
    """Test dedupe_chunk successfully finds duplicates."""
    ds = dedup_set_with_job
    mock_get_ds.return_value = ds

    redis_data = {
        "chunk:new:0": json.dumps({"file1.jpg": [1.0]}),
        "chunk:new:1": json.dumps({"file2.jpg": [2.0]}),
        "ignored:key": json.dumps([["ignored1", "ignored2"]]),
    }
    redis_conn = Mock()
    redis_conn.get.side_effect = lambda key: redis_data[key]
    mock_get_redis.return_value = redis_conn

    def dedupe_side_effect(*args, **kwargs):
        kwargs["progress"]()
        return "findings"

    mock_dedupe_images.side_effect = dedupe_side_effect

    config = {"deduplication_set_id": ds.pk, "deduplicate": {"threshold": 0.5}}
    result = dedupe_chunk.run("chunk:new:0", "chunk:new:1", "ignored:key", config)

    assert result == "findings"
    mock_notify.assert_called()
    mock_dedupe_images.assert_called_once_with(
        {"file1.jpg": [1.0]},
        {"file2.jpg": [2.0]},
        {("ignored1", "ignored2")},
        dedupe_threshold=0.5,
        options={"threshold": 0.5},
        progress=mock_dedupe_images.call_args.kwargs["progress"],
    )


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.get_redis_connection")
@patch("hope_dedup_engine.apps.faces.celery_tasks.dedupe_images", side_effect=Exception("mock error"))
@patch("hope_dedup_engine.apps.faces.celery_tasks.sentry_sdk")
def test_dedupe_chunk_error(mock_sentry, mock_dedupe_images, mock_get_redis, dedup_set_with_job):
    """Test dedupe_chunk handles exceptions correctly."""
    ds = dedup_set_with_job

    redis_data = {
        "chunk:new:0": json.dumps({"file1.jpg": [1.0]}),
        "chunk:new:1": json.dumps({"file2.jpg": [2.0]}),
        "ignored:key": json.dumps([["ignored1", "ignored2"]]),
    }
    redis_conn = Mock()
    redis_conn.get.side_effect = lambda key: redis_data[key]
    mock_get_redis.return_value = redis_conn

    with pytest.raises(Exception, match="mock error"):
        dedupe_chunk.run(
            "chunk:new:0",
            "chunk:new:1",
            "ignored:key",
            {"deduplication_set_id": ds.pk, "deduplicate": {}},
        )
    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.FAILED
    mock_sentry.capture_exception.assert_called_once()


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.get_redis_connection")
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
def test_callback_findings_error_on_update(mock_get_ds, mock_get_redis, dedup_set_with_job, mocker):
    """Test callback_findings handles exceptions during update_findings."""
    ds = dedup_set_with_job
    mock_get_ds.return_value = ds
    mocker.patch.object(ds, "update_findings", side_effect=Exception("DB Error"))

    redis_conn = Mock()
    mock_get_redis.return_value = redis_conn

    context = {"keys_to_delete": ["key1", "key2"]}
    config = {"deduplication_set_id": ds.pk}

    with pytest.raises(Exception, match="DB Error"):
        callback_findings.run([], context=context, config=config)

    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.FAILED
    redis_conn.delete.assert_called_once_with(*context["keys_to_delete"])


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.get_redis_connection")
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.send_notification")
def test_callback_findings_success(mock_send_notification, mock_get_ds, mock_get_redis, dedup_set_with_job, mocker):
    """Test callback_findings aggregates results and updates the dataset."""
    ds = dedup_set_with_job
    ImageFactory.create_batch(3, deduplication_set=ds)
    mock_get_ds.return_value = ds
    mocker.patch.object(ds, "update_findings")

    redis_conn = Mock()
    mock_get_redis.return_value = redis_conn

    results = [
        [("file1.jpg", "file2.jpg", 0.99, 1)],
        [("file2.jpg", "file1.jpg", 0.99, 1)],  # Duplicate pair
    ]
    context = {"keys_to_delete": ["key1", "key2"]}
    config = {"deduplication_set_id": ds.pk, "deduplicate": {"threshold": 0.9}}

    result = callback_findings.run(results, context=context, config=config)

    ds.refresh_from_db()
    ds.update_findings.assert_called_once_with([("file1.jpg", "file2.jpg", 0.99, 1)])
    assert ds.state == DeduplicationSet.State.READY
    mock_send_notification.assert_called_once_with(ds.notification_url)
    redis_conn.delete.assert_called_once_with(*context["keys_to_delete"])
    assert result["Findings"] == 1
    assert result["Files"] == 3
    assert result["Config"] == config["deduplicate"]


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.get_redis_connection")
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.deduplicate_dataset.delay")
def test_callback_encodings_success(mock_delay, mock_get_ds, mock_get_redis, dedup_set_with_job, mocker):
    """Test callback_encodings triggers the next step in the deduplication process."""
    ds = dedup_set_with_job
    mock_get_ds.return_value = ds
    mocker.patch.object(
        ds,
        "get_encodings",
        return_value={
            "new1.jpg": [1],
            "new2.jpg": [2],
            "existing1.jpg": [3],
        },
    )
    mocker.patch.object(ds, "get_ignored_pairs", return_value={("existing1.jpg", "existing2.jpg")})

    redis_conn = Mock()
    mock_get_redis.return_value = redis_conn

    config = {"deduplication_set_id": ds.pk}
    results = [["new1.jpg", "new2.jpg"]]

    response = callback_encodings.run(results, config=config)

    assert response == {"Encoded": True}

    assert redis_conn.set.call_count == 1 + len(results[0]) + 1  # ignored pairs + new chunks + existing chunk
    called_kwargs = mock_delay.call_args.kwargs
    assert called_kwargs["config"] == config
    assert called_kwargs["ignored_pairs_key"] == f"hde:dedup:{ds.pk}:ignored_pairs"
    assert len(called_kwargs["new_chunk_keys"]) == len(results[0])
    assert all(key.startswith(f"hde:dedup:{ds.pk}:chunk:new:") for key in called_kwargs["new_chunk_keys"])
    assert len(called_kwargs["existing_chunk_keys"]) == 1
    assert all(key.startswith(f"hde:dedup:{ds.pk}:chunk:existing:") for key in called_kwargs["existing_chunk_keys"])


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.chord")
def test_deduplicate_dataset_success(mock_chord, mock_get_ds, dedup_set_with_job):
    """Test deduplicate_dataset creates a chord of deduplication tasks."""
    ds = dedup_set_with_job
    mock_get_ds.return_value = ds
    chord_callable = Mock(return_value="sig-123")
    mock_chord.return_value = chord_callable

    config = {"deduplication_set_id": ds.pk}
    new_chunk_keys = ["new:0"]
    existing_chunk_keys: list[str] = []

    result = deduplicate_dataset.run(
        config=config,
        new_chunk_keys=new_chunk_keys,
        existing_chunk_keys=existing_chunk_keys,
        ignored_pairs_key="ignored",
    )

    assert result["tasks"] == 1
    assert result["deduplication_set"] == str(ds)
    assert result["chord_id"] == "sig-123"
    mock_chord.assert_called_once()
    header = mock_chord.call_args[0][0]
    assert len(header) == 1
    chord_callable.assert_called_once()


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.chord")
def test_deduplicate_dataset_multiple_chunks(mock_chord, mock_get_ds, dedup_set_with_job):
    """Test deduplicate_dataset with multiple new and existing chunks."""
    ds = dedup_set_with_job
    mock_get_ds.return_value = ds
    chord_callable = Mock(return_value="sig-456")
    mock_chord.return_value = chord_callable

    config = {"deduplication_set_id": ds.pk}
    new_chunk_keys = ["new:0", "new:1", "new:2"]
    existing_chunk_keys = ["existing:0", "existing:1"]

    result = deduplicate_dataset.run(
        config=config,
        new_chunk_keys=new_chunk_keys,
        existing_chunk_keys=existing_chunk_keys,
        ignored_pairs_key="ignored",
    )

    expected_task_count = len(new_chunk_keys) * (len(new_chunk_keys) + 1) // 2 + len(new_chunk_keys) * len(
        existing_chunk_keys
    )
    assert result["tasks"] == expected_task_count
    assert result["chord_id"] == "sig-456"
    mock_chord.assert_called_once()
    header = mock_chord.call_args[0][0]
    assert len(header) == expected_task_count
    chord_callable.assert_called_once()


@patch("hope_dedup_engine.apps.faces.celery_tasks.FileSyncManager")
def test_sync_dnn_files_success(mock_fsm, settings):
    """Test sync_dnn_files successfully syncs all required files."""
    settings.DNN_FILES = {"model": {"filename": "f1.dat", "sources": {"azure": "b1"}}}
    mock_fsm.return_value.downloader.sync.return_value = True
    assert sync_dnn_files.run(force=True) is True
    mock_fsm.return_value.downloader.sync.assert_called_once_with("f1.dat", "b1", force=True)


@patch("hope_dedup_engine.apps.faces.celery_tasks.sync_dnn_files.update_state")
@patch("hope_dedup_engine.apps.faces.celery_tasks.FileSyncManager", side_effect=Exception("FSM Error"))
def test_sync_dnn_files_error(mock_fsm, mock_update_state, settings):
    """Test sync_dnn_files handles exceptions and updates task state."""
    settings.DNN_FILES = {"model": {"filename": "f1.dat", "sources": {"azure": "b1"}}}
    with pytest.raises(Exception, match="FSM Error"):
        sync_dnn_files.run()

    mock_update_state.assert_called_once_with(
        state=states.FAILURE,
        meta={"exc_message": "FSM Error", "traceback": ANY},
    )
