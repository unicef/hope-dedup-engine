from celery import shared_task

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
    ignored_key_pairs: frozenset[tuple[str, str]],
    lock: DeduplicationSetLock,
) -> None:
    for first, second, score in map(_sort_keys, finder.run()):
        if (first, second) not in ignored_key_pairs:
            duplicate, _ = Duplicate.objects.get_or_create(
                deduplication_set=deduplication_set,
                first_reference_pk=first,
                second_reference_pk=second,
            )
            duplicate.score += score * finder.weight
            duplicate.save()
        lock.refresh()


HOUR = 60 * 60


@shared_task(soft_time_limit=0.5 * HOUR, time_limit=1 * HOUR)
def find_duplicates(deduplication_set_id: str, serialized_lock: str) -> None:
    deduplication_set = DeduplicationSet.objects.get(pk=deduplication_set_id)
    try:
        lock = DeduplicationSetLock.from_string(serialized_lock)

        # refresh lock in case we spent much time waiting in queue
        lock.refresh()

        # clean results
        Duplicate.objects.filter(deduplication_set=deduplication_set).delete()

        ignored_key_pairs = frozenset(
            deduplication_set.ignoredkeypair_set.values_list(
                "first_reference_pk", "second_reference_pk"
            )
        )

        weight_total = 0
        for finder in get_finders(deduplication_set):
            _save_duplicates(finder, deduplication_set, ignored_key_pairs, lock)
            weight_total += finder.weight

        for duplicate in deduplication_set.duplicate_set.all():
            duplicate.score /= weight_total
            duplicate.save()

        lock.release()

    except Exception as e:
        deduplication_set.state = DeduplicationSet.State.ERROR
        deduplication_set.error = str(e)
        deduplication_set.save()
        raise