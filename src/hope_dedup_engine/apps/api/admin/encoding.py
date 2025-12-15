from itertools import combinations

from constance import config
from deepface import DeepFace
from django.contrib.admin import ModelAdmin, register

from adminfilters.autocomplete import AutoCompleteFilter
from adminfilters.dates import DateInDateRangeFilter
from adminfilters.filters import DjangoLookupFilter
from adminfilters.mixin import AdminFiltersMixin
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django import forms
from django.http import HttpRequest
from django.shortcuts import render

from hope_dedup_engine.apps.api.models import Encoding
from hope_dedup_engine.apps.faces.managers import ImagesStorageManager


class DeduplicateForm(forms.Form):
    action = forms.CharField(widget=forms.HiddenInput)
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    min_threshold = forms.IntegerField(label="Min threshold", min_value=50, max_value=99)
    max_threshold = forms.IntegerField(label="Max threshold", min_value=51, max_value=100)

    def clean(self):
        cleaned_data = super().clean()

        min_threshold = cleaned_data.get("min_threshold")
        max_threshold = cleaned_data.get("max_threshold")

        if max_threshold <= min_threshold:
            raise ValidationError("Max threshold must be bigger than min threshold.")

        return cleaned_data


@register(Encoding)
class EncodingAdmin(AdminFiltersMixin, ModelAdmin):
    list_display = (
        "id",
        "filename",
        "deduplication_set",
        "created_at",
    )

    list_filter = (
        ("deduplication_set", AutoCompleteFilter),
        ("created_at", DateInDateRangeFilter),
        DjangoLookupFilter,
    )

    actions = ["deduplicate_selected_encodings"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def deduplicate_selected_encodings(self, request: HttpRequest, queryset: QuerySet[Encoding]):
        context = {}

        if "submit" in request.POST:
            form = DeduplicateForm(request.POST)
            if form.is_valid():
                min_threshold = form.cleaned_data["min_threshold"]
                max_threshold = form.cleaned_data["max_threshold"]
                step = round((max_threshold - min_threshold) / 10)
                thresholds = list(range(min_threshold, max_threshold + 1, step))
                thresholds[-1] = max_threshold

                storage = ImagesStorageManager()
                embeddings = []
                for encodings in queryset:
                    try:
                        representation = DeepFace.represent(
                            storage.load_image(encodings.filename),
                            model_name=config.DEFAULT_RECOGNITION_MODEL,
                            detector_backend=config.DEFAULT_DETECTOR_BACKEND,
                            max_faces=2,
                            enforce_detection=False,
                        )
                        if len(representation) > 1 or float(representation[0]["face_confidence"]) == 0.0:
                            continue

                        embeddings.append(representation[0]["embedding"])
                    except:  # noqa: E722, S110
                        pass

                confidences = []
                for pair in combinations(embeddings, 2):
                    enc1, enc2 = pair
                    output = DeepFace.verify(
                        enc1,
                        enc2,
                        model_name=config.DEFAULT_RECOGNITION_MODEL,
                        detector_backend=config.DEFAULT_DETECTOR_BACKEND,
                        distance_metric=config.DEFAULT_DISTANCE_METRIC,
                    )
                    confidences.append(output.get("confidence", 0.0))

                results = [
                    {"threshold": threshold, "count": len([c for c in confidences if c >= threshold])}
                    for threshold in thresholds
                ]
                context["results"] = results

        else:
            form = DeduplicateForm(
                initial={
                    "action": request.POST["action"],
                    "select_across": request.POST["select_across"],
                    "_selected_action": request.POST.getlist("_selected_action"),
                },
            )

        context["form"] = form

        return render(request, "admin/image/deduplicate.html", context=context)
