from unittest.mock import Mock, patch

import pytest
from celery.canvas import Signature

from hope_dedup_engine.apps.api.models import DedupJob, DeduplicationSet, Image
from hope_dedup_engine.apps.security.models import System
from hope_dedup_engine.apps.faces.celery_tasks import (
    encode_chunk,
    get_chunks,
    shadow_name,
)


@pytest.fixture
def dedup_set_with_job(db):
    """Fixture to create a DeduplicationSet with an associated DedupJob."""
    system, _ = System.objects.get_or_create(name="default")
    ds = DeduplicationSet.objects.create(reference_pk="test-set-ref", system=system)
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
    ("files", "chunk_size", "expected_chunks"),
    [
        (list(range(50)), 25, [list(range(25)), list(range(25, 50))]),
        (list(range(30)), 25, [list(range(25)), list(range(25, 30))]),
        (list(range(10)), 25, [list(range(10))]),
        ([], 25, []),
        (list(range(5)), 2, [list(range(2)), list(range(2, 4)), [4]]),
    ],
)
def test_get_chunks(files, chunk_size, expected_chunks, monkeypatch):
    """Test that get_chunks splits a list into chunks of the correct size."""
    monkeypatch.setattr("hope_dedup_engine.apps.faces.celery_tasks.CHUNK_SIZE", chunk_size)
    assert get_chunks(files) == expected_chunks


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
@patch("hope_dedup_engine.apps.faces.celery_tasks.Encoding.objects.bulk_create")
@patch("hope_dedup_engine.apps.faces.celery_tasks.DeduplicationSet.objects.get")
@patch("hope_dedup_engine.apps.faces.celery_tasks.encode_faces")
@patch("hope_dedup_engine.apps.faces.celery_tasks.notify_status")
def test_encode_chunk_success(mock_notify, mock_encode_faces, mock_get_ds, mock_bulk_create, dedup_set_with_job):
    """Test encode_chunk successfully encodes faces and saves them to the database."""
    ds = dedup_set_with_job
    mock_get_ds.return_value = ds

    # Define a side_effect function that mimics the real encode_faces
    def encode_faces_side_effect(files, options, progress):
        progress()  # This will call our notify_status callback
        return {
            "file1.jpg": [1.0],  # Success
            "file2.jpg": "NO_FACE_DETECTED",  # Error
        }

    mock_encode_faces.side_effect = encode_faces_side_effect

    encode_chunk(["file1.jpg", "file2.jpg"], {}, ds.pk)

    mock_get_ds.assert_called_once_with(pk=ds.pk)
    mock_encode_faces.assert_called_once()
    mock_notify.assert_called()
    mock_bulk_create.assert_called_once()

    # Check the contents of the bulk_create call
    created_encodings = mock_bulk_create.call_args[0][0]
    assert len(created_encodings) == 2
    enc1 = next(e for e in created_encodings if e.filename == "file1.jpg")
    enc2 = next(e for e in created_encodings if e.filename == "file2.jpg")

    assert enc1.embedding == [1.0]
    assert enc1.status_code == Image.StatusCode.DEDUPLICATE_SUCCESS.value
    assert enc2.embedding is None
    assert enc2.status_code == Image.StatusCode.NO_FACE_DETECTED.value


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.faces.celery_tasks.encode_faces", side_effect=Exception("mock error"))
@patch("hope_dedup_engine.apps.faces.celery_tasks.sentry_sdk")
def test_encode_chunk_error(mock_sentry, mock_encode_faces, dedup_set_with_job):
    """Test encode_chunk handles exceptions correctly."""
    ds = dedup_set_with_job
    with pytest.raises(Exception, match="mock error"):
        encode_chunk(["file1.jpg"], {}, ds.pk)
    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.FAILED
    mock_sentry.capture_exception.assert_called_once()
