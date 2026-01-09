from unittest.mock import ANY, Mock, patch
from enum import IntEnum
import pytest
from celery import states
from celery.canvas import Signature

from hope_dedup_engine.apps.api.models import MainJob, DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSetGroup
from hope_dedup_engine.apps.api.models.jobs import (
    SyncDnnFilesJob,
    DeduplicateDatasetJob,
    EncodeChunkJob,
    DedupeChunkJob,
    CallbackFindingsJob,
)
from hope_dedup_engine.apps.security.models import System
from hope_dedup_engine.apps.faces.celery_tasks import (
    callback_findings,
    dedupe_chunk,
    deduplicate_dataset,
    encode_chunk,
    get_chunks,
    shadow_name,
    sync_dnn_files,
    ChunkPurpose,
)


@pytest.fixture
def deduplication_set(db) -> DeduplicationSet:
    system, _ = System.objects.get_or_create(name="default")
    dsg = DeduplicationSetGroup.objects.create(reference_pk="test_group", system=system)
    return DeduplicationSet.objects.create(name="test_set", group=dsg)


@pytest.fixture
def dedup_job(deduplication_set) -> MainJob:
    """Fixture to create a DeduplicationSet with an associated DedupJob."""
    return MainJob.objects.create(deduplication_set=deduplication_set)


@pytest.fixture
def deduplicate_dataset_job(deduplication_set) -> DeduplicateDatasetJob:
    return DeduplicateDatasetJob.objects.create(deduplication_set=deduplication_set)


@pytest.fixture
def sync_dnn_files_job(db) -> SyncDnnFilesJob:
    return SyncDnnFilesJob.objects.create()


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
def test_encode_chunk_success(mock_encode_faces, mock_get_ds, dedup_job, encoding_factory):
    """Test encode_chunk successfully encodes faces and updates the dataset."""
    mock_get_ds.return_value = dedup_job.deduplication_set
    encoding = encoding_factory(
        deduplication_set=dedup_job.deduplication_set,
        filename="file1.jpg",
    )

    encode_chunk_job = EncodeChunkJob.objects.create(
        deduplication_set=dedup_job.deduplication_set, encoding_ids=[encoding.pk]
    )

    encode_chunk(encode_chunk_job.pk, encode_chunk_job.version)

    mock_encode_faces.assert_called_once_with(
        dedup_job.deduplication_set, [encoding.pk], 0.9, 0.25, "Facenet512", "retinaface", align=True
    )


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.encode_faces", side_effect=Exception("mock error"))
@patch("hope_dedup_engine.apps.faces.celery_tasks.sentry_sdk")
def test_encode_chunk_error(mock_sentry, mock_encode_faces, dedup_job, encoding_factory):
    """Test encode_chunk handles exceptions correctly."""
    encoding = encoding_factory(deduplication_set=dedup_job.deduplication_set, filename="file1.jpg")
    encode_chunk_job = EncodeChunkJob.objects.create(
        deduplication_set=dedup_job.deduplication_set, encoding_ids=[encoding.pk]
    )
    with pytest.raises(Exception, match="mock error"):
        encode_chunk(encode_chunk_job.pk, encode_chunk_job.version)
    dedup_job.deduplication_set.refresh_from_db()
    assert dedup_job.deduplication_set.state == DeduplicationSet.State.FAILED
    mock_sentry.capture_exception.assert_called_once()


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.dedupe_images")
def test_dedupe_chunk_success(mock_dedupe_images, mock_get_ds, dedup_job, encoding_factory):
    """Test dedupe_chunk successfully finds duplicates."""
    mock_get_ds.return_value = dedup_job.deduplication_set
    encoding = encoding_factory(deduplication_set=dedup_job.deduplication_set, filename="file1.jpg")
    dedup_chunk_job = DedupeChunkJob.objects.create(
        deduplication_set=dedup_job.deduplication_set, encoding_ids0=[encoding.pk], encoding_ids1=[]
    )

    dedupe_chunk(dedup_chunk_job.pk, dedup_chunk_job.version)

    mock_dedupe_images.assert_called_once_with(
        dedup_job.deduplication_set, [encoding], [], set(), 50, "Facenet512", "retinaface", "cosine", True, True
    )


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.dedupe_images", side_effect=Exception("mock error"))
@patch("hope_dedup_engine.apps.faces.celery_tasks.sentry_sdk")
def test_dedupe_chunk_error(mock_sentry, mock_dedupe_images, dedup_job, encoding_factory):
    """Test dedupe_chunk handles exceptions correctly."""
    encoding = encoding_factory(deduplication_set=dedup_job.deduplication_set, filename="file1.jpg")
    dedup_chunk_job = DedupeChunkJob.objects.create(
        deduplication_set=dedup_job.deduplication_set, encoding_ids0=[encoding.pk], encoding_ids1=[]
    )
    with pytest.raises(Exception, match="mock error"):
        dedupe_chunk(dedup_chunk_job.pk, dedup_chunk_job.version)
    dedup_job.deduplication_set.refresh_from_db()
    assert dedup_job.deduplication_set.state == DeduplicationSet.State.FAILED
    mock_sentry.capture_exception.assert_called_once()


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.send_notification")
def test_callback_findings_success(mock_send_notification, mock_get_ds, dedup_job, mocker):
    """Test callback_findings aggregates results and updates the dataset."""
    mock_get_ds.return_value = dedup_job.deduplication_set
    callback_findings_job = CallbackFindingsJob.objects.create(deduplication_set=dedup_job.deduplication_set)

    callback_findings(callback_findings_job.pk, callback_findings_job.version, None)

    dedup_job.deduplication_set.refresh_from_db()
    assert dedup_job.deduplication_set.state == DeduplicationSet.State.READY
    mock_send_notification.assert_called_once()


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.chord")
def test_deduplicate_dataset_success(mock_chord, mock_get_ds, dedup_job, mocker, encoding_factory):
    """Test deduplicate_dataset creates a chord of deduplication tasks."""
    mock_get_ds.return_value = dedup_job.deduplication_set
    encoding_factory.create_batch(3, deduplication_set=dedup_job.deduplication_set)
    deduplicate_dataset_job = DeduplicateDatasetJob.objects.create(deduplication_set=dedup_job.deduplication_set)
    result = deduplicate_dataset(deduplicate_dataset_job.pk, deduplicate_dataset_job.version, None)
    assert result["chunks"] == 1
    mock_chord.assert_called_once()


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.chord")
def test_deduplicate_dataset_multiple_chunks(
    mock_chord, mock_get_ds, deduplicate_dataset_job, monkeypatch, encoding_factory
):
    """Test deduplicate_dataset with enough encodings to create multiple chunks."""
    chunks = 3
    chunk_size = 2
    filenames_count = 2 * chunk_size + 1

    class _P(IntEnum):
        DEDUPE = chunk_size

    monkeypatch.setattr("hope_dedup_engine.apps.faces.celery_tasks.ChunkPurpose", _P)
    mock_get_ds.return_value = deduplicate_dataset_job.deduplication_set
    for i in range(filenames_count):
        encoding_factory(deduplication_set=deduplicate_dataset_job.deduplication_set, filename=f"f{i}")

    result = deduplicate_dataset(deduplicate_dataset_job.pk, deduplicate_dataset_job.version, None)

    assert result["chunks"] == chunks
    mock_chord.assert_called_once()
    header = mock_chord.call_args[0][0]
    assert len(header) == chunk_size * chunks


@patch("hope_dedup_engine.apps.faces.celery_tasks.FileSyncManager")
def test_sync_dnn_files_success(mock_fsm, settings, sync_dnn_files_job):
    """Test sync_dnn_files successfully syncs all required files."""
    settings.DNN_FILES = {"model": {"filename": "f1.dat", "sources": {"azure": "b1"}}}
    sync_dnn_files_job.force = True
    sync_dnn_files_job.save()
    mock_fsm.return_value.downloader.sync.return_value = True
    assert sync_dnn_files(sync_dnn_files_job.pk, sync_dnn_files_job.version) is True
    mock_fsm.return_value.downloader.sync.assert_called_once_with("f1.dat", "b1", force=True)


@patch("hope_dedup_engine.apps.faces.celery_tasks.sync_dnn_files.update_state")
@patch("hope_dedup_engine.apps.faces.celery_tasks.FileSyncManager", side_effect=Exception("FSM Error"))
def test_sync_dnn_files_error(mock_fsm, mock_update_state, settings, sync_dnn_files_job):
    """Test sync_dnn_files handles exceptions and updates task state."""
    settings.DNN_FILES = {"model": {"filename": "f1.dat", "sources": {"azure": "b1"}}}
    with pytest.raises(Exception, match="FSM Error"):
        sync_dnn_files(sync_dnn_files_job.pk, sync_dnn_files_job.version)

    mock_update_state.assert_called_once_with(
        state=states.FAILURE,
        meta={"exc_message": "FSM Error", "traceback": ANY},
    )
