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
    main_job_factory,
    encoding_factory,
):
    """Test that find_duplicates encodes and deduplicates in a single task."""
    job = main_job_factory()
    dedup_set = job.deduplication_set
    encoding_factory(deduplication_set=dedup_set, filename="file1.jpg", embedding=None)
    encoding_factory(deduplication_set=dedup_set, filename="file2.jpg", embedding=None)
    mock_dedupe_all.return_value = 5

    result = find_duplicates(job.id, job.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.READY
    assert mock_send_notification.call_count == 2  # start and finish
    mock_encode_faces.assert_called_once()
    mock_dedupe_all.assert_called_once()
    assert result["encodings_processed"] == 2
    assert result["findings_created"] == 5


@patch("hope_dedup_engine.apps.api.deduplication.process.dedupe_all")
@patch("hope_dedup_engine.apps.api.deduplication.process.encode_faces")
@patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")
def test_find_duplicates_encode_only(
    mock_send_notification,
    mock_encode_faces,
    mock_dedupe_all,
    main_job_factory,
    encoding_factory,
):
    """Test that find_duplicates skips deduplication when encode_only is True."""
    job = main_job_factory(encode_only=True)
    dedup_set = job.deduplication_set
    encoding_factory(deduplication_set=dedup_set, filename="file1.jpg", embedding=None)

    result = find_duplicates(job.id, job.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.READY
    mock_encode_faces.assert_called_once()
    mock_dedupe_all.assert_not_called()
    assert result["findings_created"] == 0


@patch("sentry_sdk.capture_exception")
@patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")
def test_find_duplicates_exception(
    mock_send_notification,
    mock_capture_exception,
    main_job_factory,
):
    """Test the exception handling path for the find_duplicates task."""
    # Only raise on the first call (inside try block), not on second call (in finish_processing)
    mock_send_notification.side_effect = [Exception("Test Error"), None]

    job = main_job_factory()
    dedup_set = job.deduplication_set

    with pytest.raises(Exception, match="Test Error"):
        find_duplicates(job.id, job.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.FAILED
    mock_capture_exception.assert_called()


@patch("hope_dedup_engine.apps.api.deduplication.process.find_duplicates.apply_async")
def test_find_duplicates_reschedules_when_processing(
    mock_apply_async,
    main_job_factory,
):
    """Test that find_duplicates reschedules when dataset is already being processed."""
    job = main_job_factory(deduplication_set__state=DeduplicationSet.State.PROCESSING)

    result = find_duplicates(job.id, job.version)

    assert result["status"] == "rescheduled"
    assert result["retry_in_seconds"] == RESCHEDULE_INTERVAL
    mock_apply_async.assert_called_once_with(
        args=[job.id, job.version],
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
    main_job_factory,
):
    """Test that find_duplicates proceeds when PROCESSING state is stale (>24h)."""
    job = main_job_factory(deduplication_set__state=DeduplicationSet.State.PROCESSING)
    dedup_set = job.deduplication_set
    mock_dedupe_all.return_value = 0

    DeduplicationSet.objects.filter(pk=dedup_set.pk).update(updated_at=timezone.now() - timedelta(hours=25))

    find_duplicates(job.id, job.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.READY

    mock_sentry.capture_message.assert_called_once()
    assert "Stale PROCESSING state" in mock_sentry.capture_message.call_args[0][0]
