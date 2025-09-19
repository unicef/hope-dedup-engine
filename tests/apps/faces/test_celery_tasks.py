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

import json
import os
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


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


@pytest.mark.parametrize(
    ("files", "target_chunks", "expected_num_chunks"),
    [
        (list(range(50)), 10, 10),  # 50 files, target 10 -> 10 chunks of 5
        (list(range(30)), 10, 10),  # 30 files, target 10 -> 10 chunks of 3
        (list(range(9)), 10, 9),  # 9 files, target 10 -> 9 chunks of 1
        ([], 10, 0),
        (list(range(5)), 2, 2),  # 5 files, target 2 -> 2 chunks ([0,1,2], [3,4])
    ],
)
def test_get_chunks(files, target_chunks, expected_num_chunks, monkeypatch):
    """Test that get_chunks splits a list into a target number of chunks."""
    monkeypatch.setattr("hope_dedup_engine.apps.faces.celery_tasks.TARGET_CHUNKS", target_chunks)
    chunks = get_chunks(files)
    assert len(chunks) == expected_num_chunks
    if files:
        assert sorted([item for sublist in chunks for item in sublist]) == sorted(files)


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
    result = shadow_name(Mock(), [], {}, {"chord": None})
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
        return {"file1.jpg": [1.0]}, ["file1.jpg"], 1, 0

    mock_encode_faces.side_effect = encode_side_effect

    newly_encoded = encode_chunk(["file1.jpg"], {"deduplication_set_id": ds.pk, "encoding": {}})

    mock_encode_faces.assert_called_once()
    ds.update_encodings.assert_called_once_with({"file1.jpg": [1.0]})
    assert newly_encoded == ["file1.jpg"]
    mock_notify.assert_called()


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.services.facial.DeepFace.represent")
@patch("hope_dedup_engine.apps.faces.services.facial.get_storage_manager")
def test_encode_chunk_with_local_storage(
    mock_get_storage_manager, mock_deepface, mock_get_ds, dedup_set_with_job, settings
):
    """Test encode_chunk uses the configured local storage manager."""
    settings.IMAGE_STORAGE_BACKEND = "local"

    mock_storage = Mock()
    mock_get_storage_manager.return_value = mock_storage

    ds = dedup_set_with_job
    mock_get_ds.return_value = ds
    mock_deepface.return_value = [{"embedding": [1.0]}]

    encode_chunk(["file1.jpg"], {"deduplication_set_id": ds.pk})

    mock_get_storage_manager.assert_called_once()
    mock_storage.load_image.assert_called_once_with("file1.jpg")


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.encode_faces", side_effect=Exception("mock error"))
@patch("hope_dedup_engine.apps.faces.celery_tasks.sentry_sdk")
def test_encode_chunk_error(mock_sentry, mock_encode_faces, dedup_set_with_job):
    """Test encode_chunk handles exceptions correctly."""
    ds = dedup_set_with_job
    with pytest.raises(Exception, match="mock error"):
        encode_chunk(["file1.jpg"], {"deduplication_set_id": ds.pk})
    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.FAILED
    mock_sentry.capture_exception.assert_called_once()


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.dedupe_images")
def test_dedupe_chunk_success(mock_dedupe_images, dedup_set_with_job):
    """Test dedupe_chunk successfully finds duplicates using storage files."""
    ds = dedup_set_with_job
    config = {"deduplication_set_id": ds.pk}
    cached_data_dir = f"encodings/{ds.pk}"
    chunk_path1 = os.path.join(cached_data_dir, "chunk1.json")
    chunk_path2 = os.path.join(cached_data_dir, "chunk2.json")
    ignored_pairs_path = os.path.join(cached_data_dir, "ignored_pairs.json")

    default_storage.save(chunk_path1, ContentFile(json.dumps({"f1": [1.0]}).encode()))
    default_storage.save(chunk_path2, ContentFile(json.dumps({"f2": [2.0]}).encode()))
    default_storage.save(ignored_pairs_path, ContentFile(json.dumps([]).encode()))

    mock_dedupe_images.return_value = "findings"

    result = dedupe_chunk(chunk_path1, chunk_path2, ignored_pairs_path, config)

    assert result == "findings"
    mock_dedupe_images.assert_called_once_with(
        {"f1": [1.0]},
        {"f2": [2.0]},
        set(),
        dedupe_threshold=ANY,
        options=ANY,
        progress=ANY,
    )


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.dedupe_images", side_effect=Exception("mock error"))
@patch("hope_dedup_engine.apps.faces.celery_tasks.sentry_sdk")
def test_dedupe_chunk_error(mock_sentry, mock_dedupe_images, dedup_set_with_job):
    """Test dedupe_chunk handles exceptions correctly."""
    ds = dedup_set_with_job
    config = {"deduplication_set_id": ds.pk}
    cached_data_dir = f"encodings/{ds.pk}"
    chunk_path1 = os.path.join(cached_data_dir, "chunk1.json")
    chunk_path2 = os.path.join(cached_data_dir, "chunk2.json")
    ignored_pairs_path = os.path.join(cached_data_dir, "ignored_pairs.json")

    default_storage.save(chunk_path1, ContentFile(b"{}"))
    default_storage.save(chunk_path2, ContentFile(b"{}"))
    default_storage.save(ignored_pairs_path, ContentFile(b"[]"))

    with pytest.raises(Exception, match="mock error"):
        dedupe_chunk(chunk_path1, chunk_path2, ignored_pairs_path, config)

    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.FAILED
    mock_sentry.capture_exception.assert_called_once()


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("django.core.files.storage.default_storage.delete")
def test_callback_findings_error_on_update(mock_delete, mock_get_ds, dedup_set_with_job, mocker):
    """Test callback_findings handles exceptions and still cleans up files."""
    ds = dedup_set_with_job
    mock_get_ds.return_value = ds
    mocker.patch.object(ds, "update_findings", side_effect=Exception("DB Error"))

    config = {"deduplication_set_id": ds.pk}
    cached_data_dir = f"encodings/{ds.pk}"
    num_new, num_existing = 1, 1

    with pytest.raises(Exception, match="DB Error"):
        callback_findings([], cached_data_dir, num_new, num_existing, config)

    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.FAILED
    assert mock_delete.call_count == 3
    mock_delete.assert_any_call(os.path.join(cached_data_dir, "ignored_pairs.json"))
    mock_delete.assert_any_call(os.path.join(cached_data_dir, "new_chunk_0.json"))
    mock_delete.assert_any_call(os.path.join(cached_data_dir, "existing_chunk_0.json"))


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.send_notification")
@patch("django.core.files.storage.default_storage.delete")
def test_callback_findings_success(mock_delete, mock_send_notification, mock_get_ds, dedup_set_with_job, mocker):
    """Test callback_findings aggregates results, updates dataset, and cleans up files."""
    ds = dedup_set_with_job
    mock_get_ds.return_value = ds
    mocker.patch.object(ds.image_set, "all", return_value=[1, 2, 3])
    mocker.patch.object(ds, "update_findings")
    results = [
        [("file1.jpg", "file2.jpg", 0.99, 1)],
        [("file2.jpg", "file1.jpg", 0.99, 1)],
    ]
    config = {"deduplication_set_id": ds.pk}
    cached_data_dir = f"encodings/{ds.pk}"
    num_new, num_existing = 2, 1

    result = callback_findings(results, cached_data_dir, num_new, num_existing, config)

    ds.refresh_from_db()
    ds.update_findings.assert_called_once_with([("file1.jpg", "file2.jpg", 0.99, 1)])
    assert ds.state == DeduplicationSet.State.READY
    mock_send_notification.assert_called_once()
    assert result["Findings"] == 1

    assert mock_delete.call_count == 4
    mock_delete.assert_any_call(os.path.join(cached_data_dir, "ignored_pairs.json"))
    mock_delete.assert_any_call(os.path.join(cached_data_dir, "new_chunk_1.json"))
    mock_delete.assert_any_call(os.path.join(cached_data_dir, "existing_chunk_0.json"))


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.deduplicate_dataset.delay")
@patch("django.core.files.storage.default_storage.save")
def test_callback_encodings_success(mock_save, mock_delay, mock_get_ds, dedup_set_with_job, mocker):
    """Test callback_encodings creates chunk files and triggers the next step."""
    ds = dedup_set_with_job
    mock_get_ds.return_value = ds
    mocker.patch.object(ds, "get_ignored_pairs", return_value={("f1", "f2")})
    encodings = {"new1": [1.0], "existing1": [2.0]}
    mocker.patch.object(ds, "get_encodings", return_value=encodings)

    results_from_encoding = [["new1"]]
    config = {"deduplication_set_id": ds.pk}

    result = callback_encodings(results_from_encoding, config)
    assert result == {"Encoded": True}

    cached_data_dir = f"encodings/{ds.pk}"

    assert mock_save.call_count == 3

    mock_delay.assert_called_once_with(
        config=config,
        cached_data_dir=cached_data_dir,
        num_new_chunks=1,
        num_existing_chunks=1,
    )


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.chord")
def test_deduplicate_dataset(mock_chord, dedup_set_with_job):
    """Test deduplicate_dataset creates a chord with the correct number of tasks."""
    ds = dedup_set_with_job
    config = {"deduplication_set_id": ds.pk}
    cached_data_dir = f"encodings/{ds.pk}"

    num_new, num_existing = 3, 2
    result = deduplicate_dataset(config, cached_data_dir, num_new, num_existing)

    assert result["tasks"] == 12
    mock_chord.assert_called_once()
    tasks_list = mock_chord.call_args[0][0]
    assert len(tasks_list) == 12

    callback_sig = mock_chord.return_value.call_args[0][0]
    assert callback_sig.task == callback_findings.name
    assert callback_sig.kwargs["cached_data_dir"] == cached_data_dir
    assert callback_sig.kwargs["num_new_chunks"] == num_new
    assert callback_sig.kwargs["num_existing_chunks"] == num_existing

    mock_chord.reset_mock()
    num_new, num_existing = 4, 0
    result = deduplicate_dataset(config, cached_data_dir, num_new, num_existing)
    assert result["tasks"] == 10
    assert len(mock_chord.call_args[0][0]) == 10


@patch("hope_dedup_engine.apps.faces.celery_tasks.FileSyncManager")
def test_sync_dnn_files_success(mock_fsm, settings):
    """Test sync_dnn_files successfully syncs all required files."""
    settings.DNN_FILES = {"model": {"filename": "f1.dat", "sources": {"azure": "b1"}}}
    mock_fsm.return_value.downloader.sync.return_value = True
    assert sync_dnn_files(force=True) is True
    mock_fsm.return_value.downloader.sync.assert_called_once_with("f1.dat", "b1", force=True)


@patch("hope_dedup_engine.apps.faces.celery_tasks.sync_dnn_files.update_state")
@patch("hope_dedup_engine.apps.faces.celery_tasks.FileSyncManager", side_effect=Exception("FSM Error"))
def test_sync_dnn_files_error(mock_fsm, mock_update_state, settings):
    """Test sync_dnn_files handles exceptions and updates task state."""
    settings.DNN_FILES = {"model": {"filename": "f1.dat", "sources": {"azure": "b1"}}}
    with pytest.raises(Exception, match="FSM Error"):
        sync_dnn_files()

    mock_update_state.assert_called_once_with(
        state=states.FAILURE,
        meta={"exc_message": "FSM Error", "traceback": ANY},
    )
