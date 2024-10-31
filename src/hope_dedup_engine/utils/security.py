from typing import Any

from django.conf import settings

from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSet


def is_root(request: Any, *args: Any, **kwargs: Any) -> bool:
    return (
        request.user.is_superuser
        and request.headers.get(settings.ROOT_TOKEN_HEADER) == settings.ROOT_TOKEN != ""
    )


def can_reprocess(request: Any, *args: Any, **kwargs: Any) -> bool:
    obj = args[0] if args and isinstance(args[0], DeduplicationSet) else None
    if obj:
        return any(
            (
                request.user.is_superuser and obj.state == DeduplicationSet.State.ERROR,
                is_root(request),
            )
        )
    return False
