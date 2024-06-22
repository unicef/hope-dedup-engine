from pathlib import Path

from django.conf import settings
from django.core.checks import Error, register


@register()
def example_check(app_configs, **kwargs):
    errors = []
    for t in settings.TEMPLATES:
        for d in t["DIRS"]:
            if not Path(d).is_dir():
                errors.append(
                    Error(
                        f"'{d}' is not a directory",
                        hint="Remove this directory from settings.TEMPLATES.",
                        obj=settings,
                        id="hde.E001",
                    )
                )
    return errors
