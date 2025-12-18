from django import forms
from django.core.exceptions import ValidationError

MIN_THRESHOLD = 50
MAX_THRESHOLD = 100


class FindFaceForm(forms.Form):
    min_threshold = forms.IntegerField(
        label="Min threshold", initial=MIN_THRESHOLD, min_value=MIN_THRESHOLD, max_value=MAX_THRESHOLD - 1
    )
    max_threshold = forms.IntegerField(
        label="Max threshold", initial=MAX_THRESHOLD, min_value=MIN_THRESHOLD + 1, max_value=MAX_THRESHOLD
    )

    def clean(self):
        cleaned_data = super().clean()

        min_threshold = cleaned_data.get("min_threshold")
        max_threshold = cleaned_data.get("max_threshold")

        if max_threshold is not None and min_threshold is not None and max_threshold <= min_threshold:
            raise ValidationError("Max threshold must be bigger than min threshold.")

        return cleaned_data


class DeduplicateForm(FindFaceForm):
    action = forms.CharField(widget=forms.HiddenInput)
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
