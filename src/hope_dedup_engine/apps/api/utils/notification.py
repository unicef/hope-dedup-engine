from typing import Final, Protocol

import requests
import sentry_sdk
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REQUEST_TIMEOUT: Final[int] = 5
REQUEST_RETRIES: Final[int] = 3
RETRY_BACKOFF_FACTOR: Final[float] = 0.5
RETRY_STATUSES: Final[tuple[int, ...]] = (429, 500, 502, 503, 504)
NO_NOTIFICATION_URL: Final[str] = "No notification URL configured."
NOTIFICATION_DISABLED: Final[str] = "Notification disabled."
FAILED_TO_NOTIFY: Final[str] = "Failed to notify: {error}"
RESULT_SENT: Final[str] = "sent"


class ErrorMessage(str):
    pass


class WarningMessage(str):
    pass


class Notifiable(Protocol):
    """Anything with a callback url and a switch: a biometric or a biographic set."""

    notification_url: str | None
    notify: bool


def notification_session() -> requests.Session:
    """Session that retries transient failures: connection errors and the 4xx/5xx in RETRY_STATUSES.

    Other 4xx are permanent for a callback ping, so they fail on the first attempt.
    """
    retry = Retry(
        total=REQUEST_RETRIES,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUSES,
        allowed_methods=frozenset({"GET"}),
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def send_notification(target: Notifiable, force: bool = False) -> None | ErrorMessage | WarningMessage:
    if not target.notification_url:
        return WarningMessage(NO_NOTIFICATION_URL)

    if not (target.notify or force):
        return WarningMessage(NOTIFICATION_DISABLED)

    # No credentials are attached: the notification url is self-signed by HOPE, and
    # it is caller-supplied, so sending our token there would leak it to any host.
    try:
        with notification_session() as session:
            session.get(target.notification_url, timeout=REQUEST_TIMEOUT).raise_for_status()
    except requests.RequestException as e:
        sentry_sdk.capture_exception(e)
        return ErrorMessage(FAILED_TO_NOTIFY.format(error=e))
    return None
