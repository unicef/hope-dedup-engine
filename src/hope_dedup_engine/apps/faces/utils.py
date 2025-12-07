import time
from contextlib import contextmanager
from typing import Generator

import sentry_sdk
from django.conf import settings
from hope_dedup_engine.apps.api.models import Encoding


def is_facial_error(value):
    if isinstance(value, int | str):
        return value not in {
            Encoding.StatusCode.DEDUPLICATE_SUCCESS,
            Encoding.StatusCode.DEDUPLICATE_SUCCESS.name,
            Encoding.StatusCode.DEDUPLICATE_SUCCESS.label,
        } and value in (
            Encoding.StatusCode.values + Encoding.StatusCode.names + [choice.label for choice in Encoding.StatusCode]
        )
    return False


@contextmanager
def report_long_execution(message: str, threshold_seconds: int | None = None) -> Generator:
    if threshold_seconds is None:
        threshold_seconds = settings.DEFAULT_THRESHOLD_SECONDS
    start = time.time()
    yield
    if (total := time.time() - start) > threshold_seconds:
        sentry_sdk.capture_message(f"Execution took {total} seconds: {message}")
