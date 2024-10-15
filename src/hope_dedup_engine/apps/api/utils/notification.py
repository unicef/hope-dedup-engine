from typing import Final

import requests
import sentry_sdk

REQUEST_TIMEOUT: Final[int] = 5


def send_notification(url: str | None) -> None:
    try:
        if url:
            with requests.get(url, timeout=REQUEST_TIMEOUT) as response:
                response.raise_for_status()
    except requests.RequestException as e:
        sentry_sdk.capture_exception(e)
