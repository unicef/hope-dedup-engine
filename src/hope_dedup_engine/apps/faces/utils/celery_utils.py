import hashlib
import logging
from functools import wraps

from django.conf import settings

import redis

redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)


def task_lifecycle(name: str, ttl: int) -> callable:
    def decorator(func) -> callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs) -> any:
            logger = logging.getLogger(func.__module__)
            logger.info(f"{name} task started")
            result = None

            filenames = args[0] if args else kwargs.get("filenames")
            ignore_pairs = args[1] if args else kwargs.get("ignore_pairs")
            lock_name: str = f"{name}_{_get_hash(filenames, ignore_pairs)}"
            if not _acquire_lock(lock_name, ttl):
                logger.info(f"Task {name} with brocker lock {lock_name} is already running.")
                return None

            try:
                result = func(self, *args, **kwargs)
            except Exception as e:
                logger.exception(f"{name} task failed", exc_info=e)
                raise e
            finally:
                _release_lock(lock_name)
                logger.info(f"{name} task ended")
            return result

        return wrapper

    return decorator


def _acquire_lock(lock_name: str, ttl: int = 1 * 60 * 60) -> bool:
    return redis_client.set(lock_name, "true", nx=True, ex=ttl)


def _release_lock(lock_name: str) -> None:
    redis_client.delete(lock_name)


def _get_hash(filenames: tuple[str], ignore_pairs: tuple[tuple[str, str]]) -> str:
    fn_str: str = ",".join(sorted(filenames))
    ip_sorted = sorted((min(item1, item2), max(item1, item2)) for item1, item2 in ignore_pairs)
    ip_str = ",".join(f"{item1},{item2}" for item1, item2 in ip_sorted)
    return hashlib.sha256(f"{fn_str}{ip_str}".encode()).hexdigest()
