from typing import Any

from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSetGroup


def _metadata_to_form_field(meta: dict[str, Any]) -> forms.Field:
    if "choices" in meta:
        return forms.ChoiceField(
            choices=meta["choices"],
            required=True,
            help_text=meta["help_text"],
        )
    return forms.FloatField(
        required=True,
        validators=[MinValueValidator(meta["min_value"]), MaxValueValidator(meta["max_value"])],
        help_text=meta["help_text"],
    )


class DeduplicationSetGroupSettingsForm(forms.ModelForm):
    class Meta:
        model = DeduplicationSetGroup
        fields = ()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        settings = (self.instance.settings or {}) if self.instance and self.instance.pk else {}
        for f in DeduplicationSetConfig.setting_fields(admin=True):
            self.fields[f.name] = _metadata_to_form_field(f.metadata)
            if f.name in settings:
                self.fields[f.name].initial = settings[f.name]

    def save(self, commit: bool = True) -> DeduplicationSetGroup:
        instance = super().save(commit=False)
        settings = instance.settings.copy() if instance.settings else {}
        for f in DeduplicationSetConfig.setting_fields(admin=True):
            settings[f.name] = self.cleaned_data.get(f.name)
        instance.settings = settings
        if commit:
            instance.save()
        return instance
