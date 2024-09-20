from __future__ import annotations

from base64 import b64decode, b64encode
from typing import Final, Self

from django.core.cache import cache

from constance import config
from redis.exceptions import LockNotOwnedError
from redis.lock import Lock

from hope_dedup_engine.apps.api.models import DeduplicationSet

DELIMITER: Final[str] = "|"
LOCK_IS_NOT_ENABLED = "LOCK_IS_NOT_ENABLED"


class DeduplicationSetLock:
    """
    A lock used to limit access to a specific deduplication set.
    This lock can be serialized, passed to Celery worker, and then deserialized.
    """

    class LockNotOwnedException(Exception):
        pass

    def __init__(self, name: str, token: bytes | None = None) -> None:
        # we heavily rely on Redis being used as a cache framework backend.
        redis = cache._cache.get_client()
        lock = Lock(
            redis,
            name,
            blocking=False,
            thread_local=False,
            timeout=config.DEDUPLICATION_SET_LAST_ACTION_TIMEOUT,
        )

        if token is None:
            # new lock
            if not lock.acquire():
                raise self.LockNotOwnedException
        else:
            # deserialized lock
            lock.local.token = token
            if not lock.owned():
                raise DeduplicationSetLock.LockNotOwnedException

        self.lock = lock

    def __str__(self) -> str:
        name_bytes, token_bytes = self.lock.name.encode(), self.lock.local.token
        encoded = map(b64encode, (name_bytes, token_bytes))
        string_values = map(bytes.decode, encoded)
        return DELIMITER.join(string_values)

    def refresh(self) -> None:
        try:
            self.lock.extend(config.DEDUPLICATION_SET_LAST_ACTION_TIMEOUT, True)
        except LockNotOwnedError as e:
            raise self.LockNotOwnedException from e

    def release(self) -> None:
        try:
            self.lock.release()
        except LockNotOwnedError as e:
            raise self.LockNotOwnedException from e

    @classmethod
    def for_deduplication_set(
        cls: type[Self], deduplication_set: DeduplicationSet
    ) -> Self:
        return cls(f"lock:{deduplication_set.pk}")

    @classmethod
    def from_string(cls: type[Self], serialized: str) -> Self:
        name_bytes, token_bytes = map(b64decode, serialized.split(DELIMITER))
        return cls(name_bytes.decode(), token_bytes)
