from unittest.mock import ANY, Mock, patch
from enum import IntEnum
import pytest
from celery import states
from celery.canvas import Signature

from hope_dedup_engine.apps.api.models import DedupJob, DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSetGroup
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
    ChunkPurpose,
    notify_status,
)


@pytest.fixture
def dedup_set_with_job(db):
    """Fixture to create a DeduplicationSet with an associated DedupJob."""
    system, _ = System.objects.get_or_create(name="default")
    dsg = DeduplicationSetGroup.objects.create(reference_pk="test_group", system=system)
    ds = DeduplicationSet.objects.create(name="test_set", group=dsg)
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
    ("filenames", "purpose"),
    [
        (["f0", "f1", "f2", "f3", "f4"], ChunkPurpose.ENCODE),
        (["a", "b", "c", "d", "e"], 2),
    ],
    ids=["enum", "numeric"],
)
def test_get_chunks(filenames, purpose):
    size = int(purpose)
    expected = [filenames[i : i + size] for i in range(0, len(filenames), size)]

    out = get_chunks(filenames, purpose=purpose)

    assert out == expected
    assert isinstance(out, list)
    assert all(isinstance(c, list) for c in out)


@pytest.mark.parametrize("purpose", list(ChunkPurpose))
def test_get_chunks_empty_for_all_enum_values(purpose):
    assert get_chunks([], purpose=purpose) == []


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
def test_encode_chunk_success(mock_encode_faces, mock_get_ds, dedup_set_with_job, mocker):
    """Test encode_chunk successfully encodes faces and updates the dataset."""
    ds = dedup_set_with_job
    mock_get_ds.return_value = ds
    mocker.patch.object(ds, "get_encodings", return_value={})
    mocker.patch.object(ds, "update_encodings")

    def encode_side_effect(*args, **kwargs):
        return {"file1.jpg": [1.0]}, 1, 0

    mock_encode_faces.side_effect = encode_side_effect

    encode_chunk(["file1.jpg"], {"deduplication_set_id": ds.pk, "encoding": {}})

    mock_encode_faces.assert_called_once()
    ds.update_encodings.assert_called_once_with({"file1.jpg": [1.0]})


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
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.dedupe_images")
def test_dedupe_chunk_success(mock_dedupe_images, mock_get_ds, dedup_set_with_job, mocker):
    """Test dedupe_chunk successfully finds duplicates."""
    ds = dedup_set_with_job
    mock_get_ds.return_value = ds
    mocker.patch.object(ds, "get_encodings", return_value={})
    mocker.patch.object(ds, "get_ignored_pairs", return_value=set())

    def dedupe_side_effect(*args, **kwargs):
        return "findings"

    mock_dedupe_images.side_effect = dedupe_side_effect

    result = dedupe_chunk(["file1.jpg"], [], {"deduplication_set_id": ds.pk})

    assert result == "findings"


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.dedupe_images", side_effect=Exception("mock error"))
@patch("hope_dedup_engine.apps.faces.celery_tasks.sentry_sdk")
def test_dedupe_chunk_error(mock_sentry, mock_dedupe_images, dedup_set_with_job):
    """Test dedupe_chunk handles exceptions correctly."""
    ds = dedup_set_with_job
    with pytest.raises(Exception, match="mock error"):
        dedupe_chunk(["file1.jpg"], [], {"deduplication_set_id": ds.pk})
    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.FAILED
    mock_sentry.capture_exception.assert_called_once()


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
def test_callback_findings_error_on_update(mock_get_ds, dedup_set_with_job, mocker):
    """Test callback_findings handles exceptions during update_findings."""
    ds = dedup_set_with_job
    mock_get_ds.return_value = ds
    mocker.patch.object(ds, "update_findings", side_effect=Exception("DB Error"))

    with pytest.raises(Exception, match="DB Error"):
        callback_findings([], {"deduplication_set_id": ds.pk})

    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.FAILED


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.send_notification")
def test_callback_findings_success(mock_send_notification, mock_get_ds, dedup_set_with_job, mocker):
    """Test callback_findings aggregates results and updates the dataset."""
    ds = dedup_set_with_job
    mock_get_ds.return_value = ds
    mocker.patch.object(ds.image_set, "all", return_value=[1, 2, 3])
    mocker.patch.object(ds, "update_findings")
    results = [
        [("file1.jpg", "file2.jpg", 0.99, 1)],
        [("file2.jpg", "file1.jpg", 0.99, 1)],  # Duplicate pair
    ]

    result = callback_findings(results, {"deduplication_set_id": ds.pk})

    ds.refresh_from_db()
    ds.update_findings.assert_called_once_with([("file1.jpg", "file2.jpg", 0.99, 1)])
    assert ds.state == DeduplicationSet.State.READY
    mock_send_notification.assert_called_once()
    assert result["Findings"] == 1


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.deduplicate_dataset.delay")
def test_callback_encodings_success(mock_delay, mock_get_ds, dedup_set_with_job):
    """Test callback_encodings triggers the next step in the deduplication process."""
    mock_get_ds.return_value = dedup_set_with_job
    config = {"deduplication_set_id": dedup_set_with_job.pk}
    result = callback_encodings([], config)
    assert result == {"Encoded": True}
    mock_delay.assert_called_once_with(config)


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.chord")
def test_deduplicate_dataset_success(mock_chord, mock_get_ds, dedup_set_with_job, mocker):
    """Test deduplicate_dataset creates a chord of deduplication tasks."""
    ds = dedup_set_with_job
    mock_get_ds.return_value = ds
    mocker.patch.object(ds, "get_encodings", return_value={"f1": [1], "f2": [2], "f3": [3]})
    result = deduplicate_dataset({"deduplication_set_id": ds.pk})
    assert result["chunks"] == 1
    mock_chord.assert_called_once()


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.chord")
def test_deduplicate_dataset_multiple_chunks(mock_chord, mock_get_ds, dedup_set_with_job, mocker, monkeypatch):
    """Test deduplicate_dataset with enough encodings to create multiple chunks."""
    chunks = 3
    chunk_size = 2
    filenames_count = 2 * chunk_size + 1

    class _P(IntEnum):
        DEDUPE = chunk_size

    monkeypatch.setattr("hope_dedup_engine.apps.faces.celery_tasks.ChunkPurpose", _P)
    ds = dedup_set_with_job
    mock_get_ds.return_value = ds
    encodings = {f"f{i}": [i] for i in range(filenames_count)}
    mocker.patch.object(ds, "get_encodings", return_value=encodings)

    result = deduplicate_dataset({"deduplication_set_id": ds.pk})

    assert result["chunks"] == chunks
    mock_chord.assert_called_once()
    header = mock_chord.call_args[0][0]
    assert len(header) == chunk_size * chunks


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


def test_notify_status_always_returns_true():
    result = notify_status(task=None, dedup_job_id=None)
    assert result is True
