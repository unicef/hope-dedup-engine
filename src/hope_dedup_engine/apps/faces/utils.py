import time
from contextlib import contextmanager
from typing import Generator

import sentry_sdk

from hope_dedup_engine.apps.api.models import Image


def is_facial_error(value):
    if isinstance(value, int | str):
        return value not in {
            Image.StatusCode.DEDUPLICATE_SUCCESS,
            Image.StatusCode.DEDUPLICATE_SUCCESS.name,
            Image.StatusCode.DEDUPLICATE_SUCCESS.label,
        } and value in (
            Image.StatusCode.values + Image.StatusCode.names + [choice.label for choice in Image.StatusCode]
        )
    return False


DEFAULT_THRESHOLD_SECONDS = 60


@contextmanager
def report_long_execution(message: str, threshold_seconds: int = DEFAULT_THRESHOLD_SECONDS) -> Generator:
    start = time.time()
    yield
    if (total := time.time() - start) > threshold_seconds:
        sentry_sdk.capture_message(f"Execution took {total} seconds: {message}")
