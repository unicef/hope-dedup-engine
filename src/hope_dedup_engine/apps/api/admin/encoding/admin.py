from operator import attrgetter
from typing import cast, NamedTuple

from admin_extra_buttons.decorators import button
from adminfilters.filters import LinkedAutoCompleteFilter
from adminfilters.dates import DateInDateRangeFilter
from adminfilters.filters import DjangoLookupFilter
from django.contrib.admin import register, display
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from hope_dedup_engine.apps.api.admin.encoding.forms import FindFaceForm, DeduplicateForm
from hope_dedup_engine.apps.api.admin.encoding.utils.process import detect_face, deduplicate, Finding
from hope_dedup_engine.apps.api.admin.encoding.utils.threshold import calculate_thresholds, group_by_thresholds
from hope_dedup_engine.apps.api.admin.base import BaseModelAdmin
from hope_dedup_engine.apps.api.models import Encoding
from hope_dedup_engine.apps.api.utils.data_url import inline_label, parse_data_url
from hope_dedup_engine.apps.core.permissions import can


FILE_LINK = '<a target="_blank" href="{link}">{filename}</a>'
IMAGE = '<img src="{image_url}" />'
FINDING_DETAILS = "{filename0} and {filename1} ({confidence}%)<br>"


class Result(NamedTuple):
    threshold: float
    value: str | int
    details: str


def prepare_detection_results(thresholds: list[float], confidence: float) -> list[Result]:
    return [
        Result(
            threshold=threshold, value="yes" if confidence >= threshold else "no", details=f"{confidence - threshold:+}"
        )
        for threshold in thresholds
    ]


def file_link(filename: str) -> str:
    return format_html(
        FILE_LINK, filename=filename, link=reverse("admin:api_finding_image", kwargs={"filename": filename})
    )


def prepare_deduplication_results(thresholds: list[float], grouped_findings: list[list[Finding]]) -> list[Result]:
    results = []

    # we ignore the first group as it contains findings with confidence below the first threshold
    for threshold, findings in zip(thresholds, grouped_findings[1:], strict=False):
        details = format_html_join(
            "",
            FINDING_DETAILS,
            [
                {
                    "confidence": finding.confidence,
                    "filename0": file_link(finding.encoding0.filename),
                    "filename1": file_link(finding.encoding1.filename),
                }
                for finding in findings
            ],
        )
        results.append(Result(threshold=threshold, value=len(findings), details=details))  # noqa: S308

    return results


@register(Encoding)
class EncodingAdmin(BaseModelAdmin):
    list_display = ("id", "reference_pk", "filename_pretty", "deduplication_set", "created_at")

    readonly_fields = fields = (
        "deduplication_set",
        "reference_pk",
        "filename_pretty",
        "embedding_status_code",
        "created_at",
        "image_quality_scores_sorted",
    )

    list_filter = (
        ("deduplication_set__group", LinkedAutoCompleteFilter.factory(parent=None)),
        ("deduplication_set", LinkedAutoCompleteFilter.factory(parent="deduplication_set__group")),
        ("created_at", DateInDateRangeFilter),
        DjangoLookupFilter,
    )
    list_select_related = ("deduplication_set",)

    search_fields = ("reference_pk",)

    actions = ["deduplicate_selected_encodings"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Encoding]:
        return super().get_queryset(request).defer("embedding")

    @display(description="Filename", ordering="filename")
    def filename_pretty(self, obj: Encoding) -> str:
        return inline_label(obj.filename)

    @display(description="Image quality scores")
    def image_quality_scores_sorted(self, obj: Encoding) -> str:
        if not obj.image_quality_scores:
            return "N/A"
        sorted_scores = dict(sorted(obj.image_quality_scores.items(), key=lambda x: x[1] if x[1] is not None else -1))
        return str(sorted_scores)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @button(change_form=True, permission=can.api.detect_faces)
    def detect_face(self, request: HttpRequest, pk: str) -> HttpResponse:
        encoding = cast("Encoding", self.get_object(request, pk))
        label = inline_label(encoding.filename)
        image_url = (
            encoding.filename
            if parse_data_url(encoding.filename)
            else reverse("admin:api_finding_image", kwargs={"filename": encoding.filename})
        )

        context = {
            "page_title": f"Detect face on {label}",
            "title": f"Detect face on {label}",
            "opts": Encoding._meta,
            "encoding": encoding,
            "value_title": "Face detected",
            "button_title": "Detect face",
            "details_title": "Confidence delta",
            "extra": format_html(IMAGE, image_url=image_url),  # noqa: S308
        }

        if "submit" in request.POST:
            form = FindFaceForm(request.POST)
            if form.is_valid():
                detection = detect_face(encoding)
                confidence = detection.confidence if detection else 0.0
                thresholds = calculate_thresholds(
                    form.cleaned_data["min_threshold"], form.cleaned_data["max_threshold"]
                )
                context["results"] = prepare_detection_results(thresholds, confidence)

        else:
            form = FindFaceForm()

        context["form"] = form

        return render(request, "admin/api/encoding/threshold_results.html", context=context)

    def deduplicate_selected_encodings(self, request: HttpRequest, queryset: QuerySet[Encoding]) -> HttpResponse:
        context = {
            "page_title": "Deduplicate selected encodings",
            "value_title": "Duplicate count",
            "button_title": "Deduplicate",
            "details_title": "Duplicates",
        }

        if "submit" in request.POST:
            form = DeduplicateForm(request.POST)
            if form.is_valid():
                findings = deduplicate(queryset)
                thresholds = calculate_thresholds(
                    form.cleaned_data["min_threshold"], form.cleaned_data["max_threshold"]
                )
                grouped_findings = group_by_thresholds(thresholds, findings, attrgetter("confidence"))
                context["results"] = prepare_deduplication_results(thresholds, grouped_findings)

        else:
            form = DeduplicateForm(
                initial={
                    "action": request.POST["action"],
                    "_selected_action": request.POST.getlist("_selected_action"),
                },
            )

        context["form"] = form

        return render(request, "admin/api/encoding/threshold_results.html", context=context)
