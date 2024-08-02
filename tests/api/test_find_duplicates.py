from hope_dedup_engine.apps.api.deduplication.lock import DeduplicationSetLock
from hope_dedup_engine.apps.api.deduplication.process import find_duplicates
from hope_dedup_engine.apps.api.deduplication.registry import DuplicateFinder
from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import Duplicate, Image


def test_previous_results_are_removed_before_processing(
    deduplication_set: DeduplicationSet,
    duplicate: Duplicate,
    duplicate_finders: list[DuplicateFinder],
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
) -> None:
    assert not deduplication_set.duplicate_set.count()
    find_duplicates(
        str(deduplication_set.pk),
        str(DeduplicationSetLock.for_deduplication_set(deduplication_set)),
    )
    assert deduplication_set.duplicate_set.count()


def test_ignored_key_pairs(
    deduplication_set: DeduplicationSet,
    image: Image,
    second_image: Image,
    all_duplicates_finder: DuplicateFinder,
) -> None:
    assert not deduplication_set.duplicate_set.count()
    ignored_key_pair = deduplication_set.ignoredkeypair_set.create(
        first_reference_pk=image.reference_pk,
        second_reference_pk=second_image.reference_pk,
    )
    find_duplicates(
        str(deduplication_set.pk),
        str(DeduplicationSetLock.for_deduplication_set(deduplication_set)),
    )
    ignored_key_pair.delete()
    assert not deduplication_set.duplicate_set.count()


def test_weight_is_taken_into_account(
    deduplication_set: DeduplicationSet,
    image: Image,
    second_image: Image,
    all_duplicates_finder: DuplicateFinder,
    no_duplicate_finder: DuplicateFinder,
) -> None:
    find_duplicates(
        str(deduplication_set.pk),
        str(DeduplicationSetLock.for_deduplication_set(deduplication_set)),
    )
    assert deduplication_set.duplicate_set.first().score == 0.5
