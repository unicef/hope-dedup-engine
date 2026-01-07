from typing import Any

from constance import config
from django.forms import TextInput, Textarea
from django.conf import settings


class WriteOnlyMixin:
    """Write-only widget mixin that never renders stored secrets into HTML."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.mask = getattr(settings, "CONSTANCE_DEFAULTS_MASK", "***")
        self.attrs.setdefault("placeholder", self.mask)
        self.attrs.setdefault("autocomplete", "new-password")
        self.attrs.setdefault("spellcheck", "false")

    def format_value(self, value: Any) -> str:
        return ""

    def value_from_datadict(self, data: dict[str, Any], files: Any, name: str) -> Any:
        value = data.get(name)
        if value in (None, "", self.mask):
            return getattr(config, name)
        return value


class WriteOnlyTextInput(WriteOnlyMixin, TextInput): ...


class WriteOnlyTextarea(WriteOnlyMixin, Textarea): ...
