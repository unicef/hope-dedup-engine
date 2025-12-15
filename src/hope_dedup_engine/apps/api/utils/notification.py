from typing import Final

import requests
import sentry_sdk

from hope_dedup_engine.apps.api.models import DeduplicationSet

REQUEST_TIMEOUT: Final[int] = 5


def send_notification(deduplication_set: DeduplicationSet) -> None:
    if deduplication_set.notify:
        try:
            if deduplication_set.notification_url:
                with requests.get(deduplication_set.notification_url, timeout=REQUEST_TIMEOUT) as response:
                    response.raise_for_status()
        except requests.RequestException as e:
            sentry_sdk.capture_exception(e)
