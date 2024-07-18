import hashlib
import logging
from functools import wraps
from pathlib import Path
from typing import Any

from django.conf import settings

import redis
import requests

from hope_dedup_engine.apps.faces.services.duplication_detector import (
    DuplicationDetector,
)

redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)


def task_lifecycle(name: str, ttl: int) -> callable:
    """
    Decorator to manage the lifecycle of a task with logging and distributed locking.

    Args:
        name (str): The name of the task for logging purposes.
        ttl (int): The time-to-live (TTL) for the distributed lock in seconds.

    Returns:
        Callable: The decorated function with task lifecycle management.
    """

    def decorator(func: callable) -> callable:
        @wraps(func)
        def wrapper(self: DuplicationDetector, *args: Any, **kwargs: Any) -> Any:
            logger = logging.getLogger(func.__module__)
            logger.info(f"{name} task started")
            result = None

            filenames = args[0] if args else kwargs.get("filenames")
            ignore_pairs = args[1] if args else kwargs.get("ignore_pairs")
            lock_name: str = f"{name}_{_get_hash(filenames, ignore_pairs)}"
            if not _acquire_lock(lock_name, ttl):
                logger.info(
                    f"Task {name} with brocker lock {lock_name} is already running."
                )
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


def _acquire_lock(lock_name: str, ttl: int = 1 * 60 * 60) -> bool | None:
    """
    Acquire a distributed lock using Redis.

    Args:
        lock_name (str): The name of the lock to set.
        ttl (int): The time-to-live for the lock in seconds. Default is 1 hour (3600 seconds).

    Returns:
        bool | None: True if the lock was successfully acquired, None if the lock is already set.
    """
    return redis_client.set(lock_name, "true", nx=True, ex=ttl)


def _release_lock(lock_name: str) -> None:
    """
    Release a distributed lock using Redis.

    Args:
        lock_name (str): The name of the lock to delete.
    """
    redis_client.delete(lock_name)


def _get_hash(filenames: tuple[str], ignore_pairs: tuple[tuple[str, str]]) -> str:
    """
    Generate a SHA-256 hash based on filenames and ignore pairs.

    Args:
        filenames (tuple[str]): A tuple of filenames.
        ignore_pairs (tuple[tuple[str, str]]): A tuple of pairs of filenames to ignore.

    Returns:
        str: A SHA-256 hash string representing the combination of filenames and ignore pairs.
    """
    fn_str: str = ",".join(sorted(filenames))
    ip_sorted = sorted(
        (min(item1, item2), max(item1, item2)) for item1, item2 in ignore_pairs
    )
    ip_str = ",".join(f"{item1},{item2}" for item1, item2 in ip_sorted)
    return hashlib.sha256(f"{fn_str}{ip_str}".encode()).hexdigest()


def download_file(url: str, local_path: Path, timeout: int = 3 * 60) -> bool:
    """
    Download a file from a URL to a local path.

    Args:
        url (str): The URL to download the file from.
        local_path (Path): The local path to save the downloaded file.
        timeout (int): The timeout in seconds for the HTTP request. Default is 3 minutes (180 seconds).

    Returns:
        bool: True if the file was downloaded successfully, False otherwise.
    """
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with local_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return True
