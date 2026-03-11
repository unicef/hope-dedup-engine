from typing import Any
from collections.abc import Iterator
from admin_extra_buttons.mixins import ExtraButtonsMixin
from adminfilters.mixin import AdminAutoCompleteSearchMixin, AdminFiltersMixin
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django import forms
from adminactions import actions
from admin_extra_buttons.buttons import ChoiceButton as BaseChoiceButton
from admin_extra_buttons.handlers import ChoiceHandler
from admin_extra_buttons.utils import check_permission, labelize

actions.add_to_site(admin.site)


class FixedChoiceButton(BaseChoiceButton):
    def get_choices(self) -> Iterator[dict[str, Any]]:
        namespace = self.admin_site.name
        for handler_config in self.choices:
            handler = handler_config.func.extra_buttons_handler
            obj = self.original if self.change_form and self.original and not handler.single_object_invocation else None

            if handler.permission:
                try:
                    check_permission(handler, handler.permission, self.request, obj)
                except PermissionDenied:
                    continue

            if self.change_list and handler.single_object_invocation:
                url = reverse(f"{namespace}:{handler.url_name}")
            elif not handler.single_object_invocation and self.change_form and self.original:
                url = reverse(f"{namespace}:{handler.url_name}", args=[self.context["original"].pk])
            else:
                url = None
            if url:
                yield {
                    "label": handler.config.get("label", labelize(handler.name)),
                    "url": url,
                    "selected": self.request.path == url,
                }

    def can_render(self) -> bool:
        return self.visible and self.authorized() and any(self.get_choices())


ChoiceHandler.button_class = FixedChoiceButton


class BaseModelAdmin(ExtraButtonsMixin, AdminAutoCompleteSearchMixin, AdminFiltersMixin, admin.ModelAdmin):
    @property
    def media(self) -> forms.Media:
        base = super().media
        return base + forms.Media(
            js=[],
            css={
                "screen": [
                    "admin/admin_extra.css",
                ],
            },
        )
