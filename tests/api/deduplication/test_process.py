from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from hope_dedup_engine.apps.api.deduplication.process import (
    find_duplicates,
    RESCHEDULE_INTERVAL,
)
from hope_dedup_engine.apps.api.models import DeduplicationSet

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
    """Test that find_duplicates encodes and deduplicates in a single task."""
    dedup_set = job_with_encodings.deduplication_set
    mock_dedupe_all.return_value = 5

    result = find_duplicates(job_with_encodings.id, job_with_encodings.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.READY
    assert mock_send_notification.call_count == 2
    mock_encode_faces.assert_called_once()
    mock_dedupe_all.assert_called_once()
    assert result["encodings_processed"] == 2
    assert result["findings_created"] == 5

    assert len(dedup_set.log) == 1
    log_entry = dedup_set.log[0]
    assert log_entry["action"] == "deduplicate"
    assert log_entry["encodings_processed"] == 2
    assert log_entry["findings_created"] == 5
    assert log_entry["config"] is not None
    assert "error" not in log_entry


@patch("hope_dedup_engine.apps.api.deduplication.process.dedupe_all")
@patch("hope_dedup_engine.apps.api.deduplication.process.encode_faces")
@patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")
def test_find_duplicates_encode_only(
    mock_send_notification,
    mock_encode_faces,
    mock_dedupe_all,
    encode_only_job,
):
    """Test that find_duplicates skips deduplication when encode_only is True."""
    dedup_set = encode_only_job.deduplication_set

    result = find_duplicates(encode_only_job.id, encode_only_job.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.READY
    mock_encode_faces.assert_called_once()
    mock_dedupe_all.assert_not_called()
    assert result["findings_created"] == 0

    assert len(dedup_set.log) == 1
    assert dedup_set.log[0]["action"] == "encode"
    assert "error" not in dedup_set.log[0]


@patch("sentry_sdk.capture_exception")
@patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")
def test_find_duplicates_exception(
    mock_send_notification,
    mock_capture_exception,
    job_with_encodings,
):
    """Test the exception handling path for the find_duplicates task."""
    mock_send_notification.side_effect = [Exception("Test Error"), None]
    dedup_set = job_with_encodings.deduplication_set

    with pytest.raises(Exception, match="Test Error"):
        find_duplicates(job_with_encodings.id, job_with_encodings.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.FAILED
    mock_capture_exception.assert_called()

    assert len(dedup_set.log) == 1
    log_entry = dedup_set.log[0]
    assert "error" in log_entry
    assert log_entry["config"] is None


@patch("hope_dedup_engine.apps.api.deduplication.process.find_duplicates.apply_async")
def test_find_duplicates_reschedules_when_processing(
    mock_apply_async,
    processing_job,
):
    """Test that find_duplicates reschedules when dataset is already being processed."""
    result = find_duplicates(processing_job.id, processing_job.version)

    assert result["status"] == "rescheduled"
    assert result["retry_in_seconds"] == RESCHEDULE_INTERVAL
    mock_apply_async.assert_called_once_with(
        args=[processing_job.id, processing_job.version],
        countdown=RESCHEDULE_INTERVAL,
    )


@patch("hope_dedup_engine.apps.api.deduplication.process.dedupe_all")
@patch("hope_dedup_engine.apps.api.deduplication.process.encode_faces")
@patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")
@patch("hope_dedup_engine.apps.api.deduplication.process.sentry_sdk")
def test_find_duplicates_proceeds_when_stale(
    mock_sentry,
    mock_send_notification,
    mock_encode_faces,
    mock_dedupe_all,
    processing_job,
):
    """Test that find_duplicates proceeds when PROCESSING state is stale (>24h)."""
    dedup_set = processing_job.deduplication_set
    mock_dedupe_all.return_value = 0

    DeduplicationSet.objects.filter(pk=dedup_set.pk).update(updated_at=timezone.now() - timedelta(hours=25))

    find_duplicates(processing_job.id, processing_job.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.READY

    mock_sentry.capture_message.assert_called_once()
    assert "Stale PROCESSING state" in mock_sentry.capture_message.call_args[0][0]
