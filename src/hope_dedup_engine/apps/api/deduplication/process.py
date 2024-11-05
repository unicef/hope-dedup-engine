from celery import shared_task
from constance import config

from hope_dedup_engine.apps.api.deduplication.lock import DeduplicationSetLock
from hope_dedup_engine.apps.api.deduplication.registry import (
    DuplicateFinder,
    DuplicateKeyPair,
    get_finders,
)
from hope_dedup_engine.apps.api.models import DeduplicationSet, Duplicate


def _sort_keys(pair: DuplicateKeyPair) -> DuplicateKeyPair:
    first, second, score = pair
    return *sorted((first, second)), score


def _save_duplicates(
    finder: DuplicateFinder,
    deduplication_set: DeduplicationSet,
    lock_enabled: bool,
    lock: DeduplicationSetLock,
) -> None:
    reference_pk_to_filename_mapping = dict(
        deduplication_set.image_set.values_list("reference_pk", "filename")
    )
    ignored_filename_pairs = frozenset(
        map(
            tuple,
            map(
                sorted,
                deduplication_set.ignoredfilenamepair_set.values_list(
                    "first", "second"
                ),
            ),
        )
    )

    ignored_reference_pk_pairs = frozenset(
        deduplication_set.ignoredreferencepkpair_set.values_list("first", "second")
    )

    for first, second, score in map(_sort_keys, finder.run()):
        first_filename, second_filename = sorted(
            (
                reference_pk_to_filename_mapping[first],
                reference_pk_to_filename_mapping[second],
            )
        )
        ignored = (first, second) in ignored_reference_pk_pairs or (
            first_filename,
            second_filename,
        ) in ignored_filename_pairs
        if not ignored:
            duplicate, _ = Duplicate.objects.get_or_create(
                deduplication_set=deduplication_set,
                first_reference_pk=first,
                second_reference_pk=second,
            )
            duplicate.score += score * finder.weight
            duplicate.save()
        if lock_enabled:
            lock.refresh()


HOUR = 60 * 60


@shared_task(soft_time_limit=0.5 * HOUR, time_limit=1 * HOUR)
def find_duplicates(deduplication_set_id: str, serialized_lock: str) -> None:
    deduplication_set = DeduplicationSet.objects.get(pk=deduplication_set_id)
    try:
        lock_enabled = config.DEDUPLICATION_SET_LOCK_ENABLED
        lock = (
            DeduplicationSetLock.from_string(serialized_lock) if lock_enabled else None
        )

        if lock_enabled:
            # refresh lock in case we spent much time waiting in queue
            lock.refresh()

        # clean results
        Duplicate.objects.filter(deduplication_set=deduplication_set).delete()

        weight_total = 0
        for finder in get_finders(deduplication_set):
            _save_duplicates(finder, deduplication_set, lock_enabled, lock)
            weight_total += finder.weight

        for duplicate in deduplication_set.duplicate_set.all():
            duplicate.score /= weight_total
            duplicate.save()

        deduplication_set.state = deduplication_set.State.CLEAN
        deduplication_set.save()

        if lock_enabled:
            lock.release()

    except Exception:
        deduplication_set.state = DeduplicationSet.State.ERROR
        deduplication_set.save()
        raise
