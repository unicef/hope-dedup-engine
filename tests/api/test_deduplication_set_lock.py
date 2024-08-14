from time import sleep

from pytest import fail, raises
from pytest_django.fixtures import SettingsWrapper

from hope_dedup_engine.apps.api.deduplication.lock import DeduplicationSetLock
from hope_dedup_engine.apps.api.models import DeduplicationSet


def test_basic_usage(deduplication_set: DeduplicationSet) -> None:
    try:
        lock = DeduplicationSetLock.for_deduplication_set(deduplication_set)
        lock.refresh()
        lock.release()
    except Exception as e:
        fail(f"Unexpected exception raised: {e}")


def test_can_serialize_and_deserialize(deduplication_set: DeduplicationSet) -> None:
    try:
        DeduplicationSetLock.from_string(
            str(DeduplicationSetLock.for_deduplication_set(deduplication_set))
        )
    except Exception as e:
        fail(f"Unexpected exception raised: {e}")


def test_cannot_acquire_second_lock_for_same_deduplication_set(
    deduplication_set: DeduplicationSet,
) -> None:
    DeduplicationSetLock.for_deduplication_set(deduplication_set)
    with raises(DeduplicationSetLock.LockNotOwnedException):
        DeduplicationSetLock.for_deduplication_set(deduplication_set)


def test_cannot_deserialize_released_lock(deduplication_set: DeduplicationSet) -> None:
    lock = DeduplicationSetLock.for_deduplication_set(deduplication_set)
    serialized_lock = str(lock)
    lock.release()
    with raises(DeduplicationSetLock.LockNotOwnedException):
        DeduplicationSetLock.from_string(serialized_lock)


def test_lock_is_released_after_timeout(
    deduplication_set: DeduplicationSet, settings: SettingsWrapper
) -> None:
    timeout = 0.1
    settings.DEDUPLICATION_SET_LAST_ACTION_TIMEOUT = timeout
    lock = DeduplicationSetLock.for_deduplication_set(deduplication_set)
    sleep(2 * timeout)
    with raises(DeduplicationSetLock.LockNotOwnedException):
        lock.refresh()
