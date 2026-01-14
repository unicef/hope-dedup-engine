from typing import Final

import requests
import sentry_sdk
from constance import config

from hope_dedup_engine.apps.api.models import DeduplicationSet

REQUEST_TIMEOUT: Final[int] = 5


def send_notification(deduplication_set: DeduplicationSet) -> None:
    if not (deduplication_set.notify and deduplication_set.notification_url):
        return

    token = getattr(config, "HOPE_API_TOKEN", "")
    headers = {"Authorization": f"Token {token}"} if token else None

    try:
        requests.get(deduplication_set.notification_url, headers=headers, timeout=REQUEST_TIMEOUT).raise_for_status()
    except requests.RequestException as e:
        sentry_sdk.capture_exception(e)
