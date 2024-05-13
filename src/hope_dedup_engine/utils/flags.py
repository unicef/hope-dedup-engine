from typing import Any

from django.conf import settings

from flags import conditions

from hope_dedup_engine.state import state
from hope_dedup_engine.utils.http import get_server_host


@conditions.register("development")
def development(**kwargs: Any) -> bool:
    return settings.DEBUG and get_server_host() in ["127.0.0.1", "localhost"]


@conditions.register("server_address")
def server_address(value: str, **kwargs: Any) -> bool:
    return state.request.get_host() == value
