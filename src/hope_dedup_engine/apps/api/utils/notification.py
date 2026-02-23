from typing import Final

import requests
import sentry_sdk
from constance import config

from hope_dedup_engine.apps.api.models import DeduplicationSet

REQUEST_TIMEOUT: Final[int] = 5


class ErrorMessage(str):
    pass


class WarningMessage(str):
    pass


def send_notification(deduplication_set: DeduplicationSet, force: bool = False) -> None | ErrorMessage | WarningMessage:
    if not deduplication_set.notification_url:
        return WarningMessage("No notification URL configured.")

    if not (deduplication_set.notify or force):
        return WarningMessage("Notification disabled.")

    token = getattr(config, "HOPE_API_TOKEN", "")
    headers = {"Authorization": f"Token {token}"} if token else None

    try:
        requests.get(deduplication_set.notification_url, headers=headers, timeout=REQUEST_TIMEOUT).raise_for_status()
    except requests.RequestException as e:
        sentry_sdk.capture_exception(e)
        return ErrorMessage(f"Failed to send notification: {e}.")
