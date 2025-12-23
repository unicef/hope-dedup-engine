from admin_extra_buttons.mixins import ExtraButtonsMixin
from adminfilters.mixin import AdminFiltersMixin
from django.contrib import admin
from django import forms
from adminactions import actions
from admin_extra_buttons.buttons import ChoiceButton as BaseChoiceButton
from admin_extra_buttons.handlers import ChoiceHandler

actions.add_to_site(admin.site)


class FixedChoiceButton(BaseChoiceButton):
    @property
    def enabled(self) -> bool:
        return super().enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def has_choices(self) -> bool:
        return next(self.get_choices(), None) is not None

    def can_render(self) -> bool:
        return self.visible and self.authorized() and self.has_choices


ChoiceHandler.button_class = FixedChoiceButton


class BaseModelAdmin(ExtraButtonsMixin, AdminFiltersMixin, admin.ModelAdmin):
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
