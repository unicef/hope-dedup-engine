from unittest.mock import MagicMock, call

import pytest

from hope_dedup_engine.apps.api.deduplication.process import find_duplicates
from hope_dedup_engine.apps.api.models import DedupJob, DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import Finding, Image


def test_previous_results_are_removed_before_processing(
    dedup_job: DedupJob,
    deduplication_set: DeduplicationSet,
    finding: Finding,
) -> None:
    assert deduplication_set.finding_set.count()
    find_duplicates(dedup_job.pk, dedup_job.version)
    assert not deduplication_set.finding_set.count()


def test_duplicates_are_stored(
    dedup_job: DedupJob,
    deduplication_set: DeduplicationSet,
    image: Image,
    second_image: Image,
) -> None:
    assert not deduplication_set.finding_set.count()
    find_duplicates(dedup_job.pk, dedup_job.version)
    assert deduplication_set.finding_set.count()


def test_ignored_reference_pk_pairs(
    dedup_job: DedupJob,
    deduplication_set: DeduplicationSet,
    image: Image,
    second_image: Image,
) -> None:
    assert not deduplication_set.finding_set.count()
    ignored_reference_pk_pair = deduplication_set.ignoredreferencepkpair_set.create(
        first=image.reference_pk,
        second=second_image.reference_pk,
    )
    find_duplicates(dedup_job.pk, dedup_job.version)
    ignored_reference_pk_pair.delete()
    assert not deduplication_set.finding_set.count()


def test_ignored_filename_pairs(
    dedup_job: DedupJob,
    deduplication_set: DeduplicationSet,
    image: Image,
    second_image: Image,
) -> None:
    assert not deduplication_set.finding_set.count()
    ignored_filename_pair = deduplication_set.ignoredfilenamepair_set.create(
        first=image.filename,
        second=second_image.filename,
    )
    find_duplicates(dedup_job.pk, dedup_job.version)
    ignored_filename_pair.delete()
    assert not deduplication_set.finding_set.count()


def test_weight_is_taken_into_account(
    dedup_job: DedupJob,
    deduplication_set: DeduplicationSet,
    image: Image,
    second_image: Image,
) -> None:
    find_duplicates(dedup_job.pk, dedup_job.version)
    assert deduplication_set.finding_set.first().score == 0.5


def test_notification_sent_on_successful_run(
    dedup_job: DedupJob,
    deduplication_set: DeduplicationSet,
    send_notification: MagicMock,
) -> None:
    send_notification.reset_mock()  # remove notification for CREATE state
    find_duplicates(dedup_job.pk, dedup_job.version)
    send_notification.assert_has_calls(2 * [call(deduplication_set.notification_url)])


def test_notification_sent_on_failure(
    dedup_job: DedupJob,
    deduplication_set: DeduplicationSet,
    send_notification: MagicMock,
) -> None:
    send_notification.reset_mock()  # remove notification for CREATE state
    with pytest.raises(RuntimeError):
        find_duplicates(dedup_job.pk, dedup_job.version)
    deduplication_set.refresh_from_db()
    assert deduplication_set.state == deduplication_set.State.DIRTY
    send_notification.assert_has_calls(2 * [call(deduplication_set.notification_url)])
