from unittest.mock import MagicMock

from pytest import mark, raises

from hope_dedup_engine.apps.api.deduplication.lock import DeduplicationSetLock
from hope_dedup_engine.apps.api.deduplication.process import find_duplicates
from hope_dedup_engine.apps.api.deduplication.registry import DuplicateFinder
from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import Duplicate, Image


def test_previous_results_are_removed_before_processing(
    deduplication_set: DeduplicationSet,
    duplicate: Duplicate,
    duplicate_finders: list[DuplicateFinder],
    requests_get_mock: MagicMock,
) -> None:
    assert deduplication_set.duplicate_set.count()
    find_duplicates(
        str(deduplication_set.pk),
        str(DeduplicationSetLock.for_deduplication_set(deduplication_set)),
    )
    assert not deduplication_set.duplicate_set.count()


def test_duplicates_are_stored(
    deduplication_set: DeduplicationSet,
    image: Image,
    second_image: Image,
    all_duplicates_finder: DuplicateFinder,
    requests_get_mock: MagicMock,
) -> None:
    assert not deduplication_set.duplicate_set.count()
    find_duplicates(
        str(deduplication_set.pk),
        str(DeduplicationSetLock.for_deduplication_set(deduplication_set)),
    )
    assert deduplication_set.duplicate_set.count()


def test_ignored_reference_pk_pairs(
    deduplication_set: DeduplicationSet,
    image: Image,
    second_image: Image,
    all_duplicates_finder: DuplicateFinder,
    requests_get_mock: MagicMock,
) -> None:
    assert not deduplication_set.duplicate_set.count()
    ignored_reference_pk_pair = deduplication_set.ignoredreferencepkpair_set.create(
        first=image.reference_pk,
        second=second_image.reference_pk,
    )
    find_duplicates(
        str(deduplication_set.pk),
        str(DeduplicationSetLock.for_deduplication_set(deduplication_set)),
    )
    ignored_reference_pk_pair.delete()
    assert not deduplication_set.duplicate_set.count()


def test_ignored_filename_pairs(
    deduplication_set: DeduplicationSet,
    image: Image,
    second_image: Image,
    all_duplicates_finder: DuplicateFinder,
) -> None:
    assert not deduplication_set.duplicate_set.count()
    ignored_filename_pair = deduplication_set.ignoredfilenamepair_set.create(
        first=image.filename,
        second=second_image.filename,
    )
    find_duplicates(
        str(deduplication_set.pk),
        str(DeduplicationSetLock.for_deduplication_set(deduplication_set)),
    )
    ignored_filename_pair.delete()
    assert not deduplication_set.duplicate_set.count()


def test_weight_is_taken_into_account(
    deduplication_set: DeduplicationSet,
    image: Image,
    second_image: Image,
    all_duplicates_finder: DuplicateFinder,
    no_duplicate_finder: DuplicateFinder,
    requests_get_mock: MagicMock,
) -> None:
    find_duplicates(
        str(deduplication_set.pk),
        str(DeduplicationSetLock.for_deduplication_set(deduplication_set)),
    )
    assert deduplication_set.duplicate_set.first().score == 0.5


@mark.parametrize(
    (
        "deduplication_set__notification_url",
        "deduplication_set__state",
        "notification_send",
        "new_state",
    ),
    [
        (None, 0, False, 0),
        ("", 0, False, 0),
        ("https://example.com", 0, True, 1),
        ("https://example.com", 1, True, 1),
    ],
)
def test_notification_sent_on_successful_run(
    notification_send: bool,
    new_state: int,
    deduplication_set: DeduplicationSet,
    duplicate_finders: list[DuplicateFinder],
    send_notification: MagicMock,
    requests_get_mock: MagicMock,
) -> None:
    deduplication_set.state = new_state
    find_duplicates(
        str(deduplication_set.pk),
        str(DeduplicationSetLock.for_deduplication_set(deduplication_set)),
    )

    if notification_send:
        send_notification.assert_called_once()
    else:
        send_notification.assert_not_called()


def test_notification_sent_on_failure(
    deduplication_set: DeduplicationSet,
    failing_duplicate_finder: DuplicateFinder,
    send_notification: MagicMock,
    requests_get_mock: MagicMock,
) -> None:
    with raises(Exception):
        find_duplicates(
            str(deduplication_set.pk),
            str(DeduplicationSetLock.for_deduplication_set(deduplication_set)),
        )
        assert deduplication_set.state == deduplication_set.State.ERROR
        send_notification.assert_called_once()
