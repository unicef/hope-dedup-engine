from unittest.mock import PropertyMock, patch

import pytest
from celery.exceptions import Ignore

from hope_dedup_engine.apps.api.deduplication.process import find_duplicates
from hope_dedup_engine.apps.api.models import DeduplicationSet, MainJob
from hope_dedup_engine.apps.api.models.jobs import GracefulJobCancellationError

pytestmark = pytest.mark.django_db


@patch("hope_dedup_engine.apps.api.deduplication.process.dedupe_all")
@patch("hope_dedup_engine.apps.api.deduplication.process.encode_faces")
@patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")
def test_find_duplicates_full_process(
    mock_send_notification,
    mock_encode_faces,
    mock_dedupe_all,
    job_with_encodings,
):
    dedup_set = job_with_encodings.deduplication_set
    mock_dedupe_all.return_value = 5

    result = find_duplicates(job_with_encodings.id, job_with_encodings.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.DEDUPLICATED
    mock_encode_faces.assert_called_once()
    mock_dedupe_all.assert_called_once()
    assert mock_encode_faces.call_args.kwargs["job"].pk == job_with_encodings.pk
    assert mock_dedupe_all.call_args.kwargs["job"].pk == job_with_encodings.pk
    assert result["encodings_processed"] == 2
    assert result["findings_created"] == 5

    assert len(dedup_set.log) == 1
    log_entry = dedup_set.log[0]
    assert log_entry["action"] == "deduplicate"
    assert log_entry["encodings_processed"] == 2
    assert log_entry["findings_created"] == 5
    assert log_entry["config"] is not None
    assert "error" not in log_entry

    assert not dedup_set.group.processing_locked


@patch("hope_dedup_engine.apps.api.deduplication.process.dedupe_all")
@patch("hope_dedup_engine.apps.api.deduplication.process.encode_faces")
@patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")
def test_find_duplicates_encode_only(
    mock_send_notification,
    mock_encode_faces,
    mock_dedupe_all,
    encode_only_job,
):
    dedup_set = encode_only_job.deduplication_set

    result = find_duplicates(encode_only_job.id, encode_only_job.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.ENCODED
    mock_encode_faces.assert_called_once()
    mock_dedupe_all.assert_not_called()
    assert result["findings_created"] == 0

    assert len(dedup_set.log) == 1
    assert dedup_set.log[0]["action"] == "encode"
    assert "error" not in dedup_set.log[0]

    assert not dedup_set.group.processing_locked


@patch("sentry_sdk.capture_exception")
@patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")
def test_find_duplicates_encoding_failure(
    mock_send_notification,
    mock_capture_exception,
    job_with_encodings,
):
    mock_send_notification.side_effect = [Exception("Test Error"), None, None]
    dedup_set = job_with_encodings.deduplication_set

    with pytest.raises(Exception, match="Test Error"):
        find_duplicates(job_with_encodings.id, job_with_encodings.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.ENCODING_FAILED
    mock_capture_exception.assert_called()

    assert len(dedup_set.log) == 1
    log_entry = dedup_set.log[0]
    assert "error" in log_entry
    assert log_entry["config"] is None

    assert not dedup_set.group.processing_locked


@patch("sentry_sdk.capture_exception")
@patch("hope_dedup_engine.apps.api.deduplication.process.dedupe_all")
@patch("hope_dedup_engine.apps.api.deduplication.process.encode_faces")
@patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")
def test_find_duplicates_deduplication_failure(
    mock_send_notification,
    mock_encode_faces,
    mock_dedupe_all,
    mock_capture_exception,
    job_with_encodings,
):
    mock_dedupe_all.side_effect = Exception("Dedup Error")
    dedup_set = job_with_encodings.deduplication_set

    with pytest.raises(Exception, match="Dedup Error"):
        find_duplicates(job_with_encodings.id, job_with_encodings.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.DEDUPLICATION_FAILED
    assert dedup_set.error is not None
    mock_capture_exception.assert_called()

    assert len(dedup_set.log) == 1
    assert "error" in dedup_set.log[0]

    assert not dedup_set.group.processing_locked


@patch("sentry_sdk.capture_exception")
@patch("hope_dedup_engine.apps.api.deduplication.process.dedupe_all")
@patch("hope_dedup_engine.apps.api.deduplication.process.encode_faces")
@patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")
def test_find_duplicates_cancelled_before_encoding(
    mock_send_notification,
    mock_encode_faces,
    mock_dedupe_all,
    mock_capture_exception,
    job_with_encodings,
    mocker,
):
    mocker.patch.object(MainJob, "is_termination_requested", new_callable=PropertyMock, return_value=True)
    cancel_mock = mocker.patch.object(MainJob, "cancel")
    update_state_mock = mocker.patch.object(find_duplicates, "update_state")
    dedup_set = job_with_encodings.deduplication_set

    with pytest.raises(Ignore):
        find_duplicates(job_with_encodings.id, job_with_encodings.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.ENCODING_FAILED
    mock_encode_faces.assert_not_called()
    mock_dedupe_all.assert_not_called()
    mock_capture_exception.assert_not_called()
    cancel_mock.assert_called()
    update_state_mock.assert_called_once_with(
        state="REVOKED",
        meta={
            "exc_type": "GracefulJobCancellationError",
            "exc_module": GracefulJobCancellationError.__module__,
            "exc_message": f"Cancellation requested for job #{job_with_encodings.pk}",
        },
    )
    assert "error" in dedup_set.log[0]
    assert not dedup_set.group.processing_locked


@patch("sentry_sdk.capture_exception")
@patch("hope_dedup_engine.apps.api.deduplication.process.dedupe_all")
@patch("hope_dedup_engine.apps.api.deduplication.process.encode_faces")
@patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")
def test_find_duplicates_cancelled_during_encoding(
    mock_send_notification,
    mock_encode_faces,
    mock_dedupe_all,
    mock_capture_exception,
    job_with_encodings,
    mocker,
):
    mock_encode_faces.side_effect = GracefulJobCancellationError("cancel requested")
    cancel_mock = mocker.patch.object(MainJob, "cancel")
    update_state_mock = mocker.patch.object(find_duplicates, "update_state")
    dedup_set = job_with_encodings.deduplication_set

    with pytest.raises(Ignore):
        find_duplicates(job_with_encodings.id, job_with_encodings.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.ENCODING_FAILED
    mock_dedupe_all.assert_not_called()
    mock_capture_exception.assert_not_called()
    cancel_mock.assert_called()
    update_state_mock.assert_called_once_with(
        state="REVOKED",
        meta={
            "exc_type": "GracefulJobCancellationError",
            "exc_module": GracefulJobCancellationError.__module__,
            "exc_message": "cancel requested",
        },
    )
    assert not dedup_set.group.processing_locked


@patch("sentry_sdk.capture_exception")
@patch("hope_dedup_engine.apps.api.deduplication.process.dedupe_all")
@patch("hope_dedup_engine.apps.api.deduplication.process.encode_faces")
@patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")
def test_find_duplicates_cancelled_during_deduplication(
    mock_send_notification,
    mock_encode_faces,
    mock_dedupe_all,
    mock_capture_exception,
    job_with_encodings,
    mocker,
):
    mock_dedupe_all.side_effect = GracefulJobCancellationError("cancel requested")
    mocker.patch.object(MainJob, "cancel")
    mocker.patch.object(find_duplicates, "update_state")
    dedup_set = job_with_encodings.deduplication_set

    with pytest.raises(Ignore):
        find_duplicates(job_with_encodings.id, job_with_encodings.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.DEDUPLICATION_FAILED
    mock_encode_faces.assert_called_once()
    mock_capture_exception.assert_not_called()
    assert not dedup_set.group.processing_locked
