from typing import Any

from hope_dedup_engine.apps.api.models import Image


def coerce_status_code(value: Any) -> Image.StatusCode | None:
    if value is None:
        return None

    if isinstance(value, Image.StatusCode):
        return value

    try:
        return Image.StatusCode(value)
    except (ValueError, TypeError):
        pass

    if isinstance(value, str):
        try:
            return Image.StatusCode[value]
        except KeyError:
            pass

        for status in Image.StatusCode:
            if value == status.label:
                return status

    return None


def is_facial_error(value: Any) -> bool:
    status = coerce_status_code(value)
    return status is not None and status != Image.StatusCode.DEDUPLICATE_SUCCESS
