from typing import Any
from functools import partial
from django.http import HttpRequest


def _has_perm(permission: str, request: HttpRequest, obj: Any | None = None, handler: Any | None = None) -> bool:
    user = request.user
    if obj is None:
        return user.has_perm(permission)
    return user.has_perm(permission, obj) or user.has_perm(permission)


class Can:
    def __init__(self, app_label: str | None = None) -> None:
        self._app_label = app_label

    def __call__(self, *_: object, **__: object) -> None:
        raise TypeError("Use can.<app_label>.<perm_codename>, e.g. can.api.remove_data")

    def __getattr__(self, name: str) -> Any:
        if self._app_label is None:
            return type(self)(name)
        return partial(_has_perm, f"{self._app_label}.{name}")


can = Can()
