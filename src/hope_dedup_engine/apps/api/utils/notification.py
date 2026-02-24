from typing import Final

import requests
import sentry_sdk
from constance import config

from hope_dedup_engine.apps.api.models import DeduplicationSet

REQUEST_TIMEOUT: Final[int] = 5
NO_NOTIFICATION_URL: Final[str] = "No notification URL configured."
NOTIFICATION_DISABLED: Final[str] = "Notification disabled."
FAILED_TO_NOTIFY: Final[str] = "Failed to notify: {error}"


class ErrorMessage(str):
    pass


class WarningMessage(str):
    pass


def send_notification(deduplication_set: DeduplicationSet, force: bool = False) -> None | ErrorMessage | WarningMessage:
    if not deduplication_set.notification_url:
        return WarningMessage(NO_NOTIFICATION_URL)

    if not (deduplication_set.notify or force):
        return WarningMessage(NOTIFICATION_DISABLED)

    token = getattr(config, "HOPE_API_TOKEN", "")
    headers = {"Authorization": f"Token {token}"} if token else None

    try:
        requests.get(deduplication_set.notification_url, headers=headers, timeout=REQUEST_TIMEOUT).raise_for_status()
    except requests.RequestException as e:
        sentry_sdk.capture_exception(e)
        return ErrorMessage(FAILED_TO_NOTIFY.format(error=e))
