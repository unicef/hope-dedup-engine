import contextlib
from itertools import combinations
from typing import cast

from admin_extra_buttons.decorators import button
from admin_extra_buttons.mixins import ExtraButtonsMixin
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
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from hope_dedup_engine.apps.api.models import Encoding
from hope_dedup_engine.apps.faces.managers import ImagesStorageManager


class FindFaceForm(forms.Form):
    min_threshold = forms.IntegerField(label="Min threshold", initial=(initial := 50), min_value=initial, max_value=99)
    max_threshold = forms.IntegerField(label="Max threshold", initial=(initial := 100), min_value=51, max_value=initial)

    def clean(self):
        cleaned_data = super().clean()

        min_threshold = cleaned_data.get("min_threshold")
        max_threshold = cleaned_data.get("max_threshold")

        if max_threshold <= min_threshold:
            raise ValidationError("Max threshold must be bigger than min threshold.")

        return cleaned_data


class DeduplicateForm(FindFaceForm):
    action = forms.CharField(widget=forms.HiddenInput)
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)


NUMBER_OF_THRESHOLD_VALUES = 10


def calculate_thresholds(min_threshold: int, max_threshold: int) -> list[int]:
    step = (max_threshold - min_threshold) / (NUMBER_OF_THRESHOLD_VALUES - 1)
    thresholds = [min_threshold + step * i for i in range(NUMBER_OF_THRESHOLD_VALUES)]
    thresholds[-1] = max_threshold
    return sorted(set(map(round, thresholds)))


@register(Encoding)
class EncodingAdmin(ExtraButtonsMixin, AdminFiltersMixin, ModelAdmin):
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

    search_fields = ("reference_pk",)

    actions = ["deduplicate_selected_encodings"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @button(change_form=True)
    def detect_face(self, request: HttpRequest, pk: str) -> HttpResponse:
        context = {"value_title": "Face detected", "button_title": "Detect face"}

        if "submit" in request.POST:
            form = FindFaceForm(request.POST)
            if form.is_valid():
                encoding = cast("Encoding", self.get_object(request, pk))
                confidence = 0.0
                with contextlib.suppress(Exception):
                    representation = DeepFace.represent(
                        ImagesStorageManager().load_image(encoding.filename),
                        model_name=config.DEFAULT_RECOGNITION_MODEL,
                        detector_backend=config.DEFAULT_DETECTOR_BACKEND,
                        max_faces=2,
                        enforce_detection=False,
                    )
                    if len(representation) == 1:
                        confidence = 100 * float(representation[0]["face_confidence"])

                results = [
                    {"threshold": threshold, "value": "yes" if confidence >= threshold else "no"}
                    for threshold in calculate_thresholds(
                        form.cleaned_data["min_threshold"], form.cleaned_data["max_threshold"]
                    )
                ]
                context["results"] = results

        else:
            form = FindFaceForm()

        context["form"] = form

        return render(request, "admin/image/deduplicate.html", context=context)

    def deduplicate_selected_encodings(self, request: HttpRequest, queryset: QuerySet[Encoding]) -> HttpResponse:
        context = {"value_title": "Duplicate count", "button_title": "Deduplicate"}

        if "submit" in request.POST:
            form = DeduplicateForm(request.POST)
            if form.is_valid():
                storage = ImagesStorageManager()
                embeddings = []
                for encodings in queryset:
                    with contextlib.suppress(Exception):
                        representation = DeepFace.represent(
                            storage.load_image(encodings.filename),
                            model_name=config.DEFAULT_RECOGNITION_MODEL,
                            detector_backend=config.DEFAULT_DETECTOR_BACKEND,
                            max_faces=2,
                            enforce_detection=False,
                        )
                        if (
                            len(representation) > 1
                            or float(representation[0]["face_confidence"])
                            < config.DEFAULT_FACE_DETECTION_CONFIDENCE_THRESHOLD
                        ):
                            continue

                        embeddings.append(representation[0]["embedding"])

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
                    {"threshold": threshold, "value": len([c for c in confidences if c >= threshold])}
                    for threshold in calculate_thresholds(
                        form.cleaned_data["min_threshold"], form.cleaned_data["max_threshold"]
                    )
                ]
                context["results"] = results

        else:
            form = DeduplicateForm(
                initial={
                    "action": request.POST["action"],
                    "_selected_action": request.POST.getlist("_selected_action"),
                },
            )

        context["form"] = form

        return render(request, "admin/image/deduplicate.html", context=context)
