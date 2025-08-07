import os
from typing import Any

from django.http import HttpRequest

from hope_dedup_engine.state import state


def current_state(request: HttpRequest) -> dict[str, Any]:
    return {
        "state": state,
        "app": {
            "build_date": os.environ.get("BUILD_DATE", ""),
            "commit": os.environ.get("SOURCE_COMMIT", "-"),
        },
    }
