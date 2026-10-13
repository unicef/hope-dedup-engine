"""Admin form editing a program's thresholds, the biometric `DeduplicationSetGroupSettingsForm` pattern.

One form field per `BiographicConfig` setting, read from and written to
`BiographicGroup.settings`. Unlike biometric, a change is never refused: a run
reads its config once when it starts, and every finding carries the snapshot it
was scored with, so a new threshold only affects the next run.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from django import forms
from django.core.validators import MinValueValidator

from hope_dedup_engine.apps.biographic.config import BiographicConfig, get_default_group_settings
from hope_dedup_engine.apps.biographic.models import BiographicGroup

if TYPE_CHECKING:
    GroupModelForm = forms.ModelForm[BiographicGroup]
else:
    # `ModelForm` is only generic in django-stubs, not at runtime.
    GroupModelForm = forms.ModelForm


def _form_field(meta: Mapping[str, Any]) -> forms.Field:
    field_class = forms.FloatField if meta["kind"] is float else forms.IntegerField
    return field_class(required=True, validators=[MinValueValidator(meta["min_value"])], help_text=meta["help_text"])


class BiographicGroupSettingsForm(GroupModelForm):
    class Meta:
        model = BiographicGroup
        fields = ()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # A setting added since the group was created has no snapshot yet; show
        # the Constance default the run would use for it.
        settings = {**get_default_group_settings(), **(self.instance.settings or {})}
        for f in BiographicConfig.setting_fields():
            self.fields[f.name] = _form_field(f.metadata)
            self.fields[f.name].initial = settings.get(f.name)

    def save(self, commit: bool = True) -> BiographicGroup:
        instance = super().save(commit=False)
        settings = dict(instance.settings or {})
        for f in BiographicConfig.setting_fields():
            settings[f.name] = self.cleaned_data[f.name]
        instance.settings = settings
        if commit:
            instance.save(update_fields=["settings"])
        return instance
