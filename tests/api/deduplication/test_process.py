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


@patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")
@patch("hope_dedup_engine.apps.api.deduplication.process.deduplicate_dataset")
@patch("hope_dedup_engine.apps.api.deduplication.process.encode_chunk")
@patch("hope_dedup_engine.apps.api.deduplication.process.chord")
def test_find_duplicates_orchestration(
    mock_chord,
    mock_encode_chunk,
    mock_deduplicate_dataset,
    mock_send_notification,
    dedup_job_factory,
    encoding_factory,
    finding_factory,
):
    """Test that find_duplicates correctly orchestrates Celery tasks."""
    job = dedup_job_factory()
    dedup_set = job.deduplication_set
    encoding_factory(deduplication_set=dedup_set, filename="file1.jpg", embedding=None)
    encoding_factory(deduplication_set=dedup_set, filename="file2.jpg", embedding=None)
    finding_factory(deduplication_set=dedup_set, score=100, status_code=200)
    assert dedup_set.finding_set.count() == 1

    find_duplicates(job.id, job.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.PROCESSING
    mock_send_notification.assert_called_once_with(dedup_set.notification_url)

    job.refresh_from_db()
    assert job.progress == 0

    assert mock_encode_chunk.s.call_count == 1
    mock_chord.assert_called_once_with([mock_encode_chunk.s.return_value])
    mock_deduplicate_dataset.si.assert_called_once()
    mock_chord.return_value.assert_called_once_with(mock_deduplicate_dataset.si.return_value)


@patch("sentry_sdk.capture_exception")
@patch(
    "hope_dedup_engine.apps.api.deduplication.process.send_notification",
    side_effect=Exception("Test Error"),
)
def test_find_duplicates_exception(
    mock_send_notification,
    mock_capture_exception,
    dedup_job_factory,
):
    """Test the exception handling path for the find_duplicates task."""
    job = dedup_job_factory()
    dedup_set = job.deduplication_set

    with pytest.raises(Exception, match="Test Error"):
        find_duplicates(job.id, job.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.FAILED
    mock_capture_exception.assert_called()


@patch("hope_dedup_engine.apps.api.deduplication.process.find_duplicates.apply_async")
def test_find_duplicates_reschedules_when_processing(
    mock_apply_async,
    dedup_job_factory,
):
    """Test that find_duplicates reschedules when dataset is already being processed."""
    job = dedup_job_factory(deduplication_set__state=DeduplicationSet.State.PROCESSING)

    result = find_duplicates(job.id, job.version)

    assert result["status"] == "rescheduled"
    assert result["retry_in_seconds"] == RESCHEDULE_INTERVAL
    mock_apply_async.assert_called_once_with(
        args=[job.id, job.version],
        countdown=RESCHEDULE_INTERVAL,
    )


@patch("hope_dedup_engine.apps.api.deduplication.process.chord")
@patch("hope_dedup_engine.apps.api.deduplication.process.encode_chunk")
@patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")
@patch("hope_dedup_engine.apps.api.deduplication.process.sentry_sdk")
def test_find_duplicates_proceeds_when_stale(
    mock_sentry,
    mock_send_notification,
    mock_encode_chunk,
    mock_chord,
    dedup_job_factory,
):
    """Test that find_duplicates proceeds when PROCESSING state is stale (>24h)."""
    job = dedup_job_factory(deduplication_set__state=DeduplicationSet.State.PROCESSING)
    dedup_set = job.deduplication_set

    DeduplicationSet.objects.filter(pk=dedup_set.pk).update(updated_at=timezone.now() - timedelta(hours=25))

    find_duplicates(job.id, job.version)

    dedup_set.refresh_from_db()
    assert dedup_set.state == DeduplicationSet.State.PROCESSING

    mock_sentry.capture_message.assert_called_once()
    assert "Stale PROCESSING state" in mock_sentry.capture_message.call_args[0][0]
