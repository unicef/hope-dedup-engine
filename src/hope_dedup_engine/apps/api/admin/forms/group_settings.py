from typing import Any

from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator

from hope_dedup_engine.apps.api.const import (
    DETECTOR_BACKEND_CHOICES,
    DISTANCE_METRIC_CHOICES,
    RECOGNITION_MODEL_CHOICES,
)
from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSetGroup

SETTINGS_FIELDS = (
    "recognition_model",
    "detector_backend",
    "distance_metric",
    "face_detection_confidence_threshold",
    "face_coverage_threshold",
    "duplicate_confidence_threshold",
)


class DeduplicationSetGroupSettingsForm(forms.ModelForm):
    recognition_model = forms.ChoiceField(
        choices=RECOGNITION_MODEL_CHOICES,
        required=True,
        help_text="Face recognition model for encoding face landmarks.",
    )
    detector_backend = forms.ChoiceField(
        choices=DETECTOR_BACKEND_CHOICES,
        required=True,
        help_text="Face detector backend for detecting faces in images.",
    )
    distance_metric = forms.ChoiceField(
        choices=DISTANCE_METRIC_CHOICES,
        required=True,
        help_text="Metric for measuring similarity between face embeddings.",
    )
    face_detection_confidence_threshold = forms.FloatField(
        required=False,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Minimum confidence score (0-1) for a detected face to be accepted.",
    )
    face_coverage_threshold = forms.FloatField(
        required=False,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Minimum ratio of image area (0-1) that must be covered by the face.",
    )
    duplicate_confidence_threshold = forms.FloatField(
        required=False,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Threshold on face match confidence (0-1) for treating pairs as duplicates.",
    )

    class Meta:
        model = DeduplicationSetGroup
        fields = ("reference_pk", "name", "system", "deleted")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            settings = self.instance.settings or {}
            for field_name in SETTINGS_FIELDS:
                if field_name in settings:
                    self.fields[field_name].initial = settings[field_name]

    def save(self, commit: bool = True) -> DeduplicationSetGroup:
        instance = super().save(commit=False)
        settings = instance.settings.copy() if instance.settings else {}
        for field_name in SETTINGS_FIELDS:
            value = self.cleaned_data.get(field_name)
            if value is not None and value != "":
                settings[field_name] = value
            elif field_name in settings:
                del settings[field_name]
        instance.settings = settings
        if commit:
            instance.save()
        return instance
