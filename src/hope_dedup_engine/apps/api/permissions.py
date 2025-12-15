from typing import Any

from django.http import HttpRequest


def can_view_finding_details(request: HttpRequest, obj: Any | None = None, **kwargs: Any) -> bool:
    return request.user.has_perm("api.view_finding_details")
