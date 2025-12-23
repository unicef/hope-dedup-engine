from typing import cast

from admin_extra_buttons.mixins import confirm_action
from adminfilters.autocomplete import AutoCompleteFilter
from admin_extra_buttons.api import button, choice, view
from admin_extra_buttons.buttons import ChoiceButton
from adminfilters.dates import DateInDateRangeFilter
from adminfilters.filters import ChoicesFieldComboFilter, DjangoLookupFilter
from django.contrib.admin import register
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from hope_dedup_engine.apps.api.models import DeduplicationSet, DedupJob
from hope_dedup_engine.apps.api.admin.base import BaseModelAdmin
from hope_dedup_engine.apps.api.utils.export import export_as_csv


@register(DeduplicationSet)
class DeduplicationSetAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "name",
        "group",
        "state",
        "created_at",
        "updated_at",
    )
    readonly_fields = (
        "id",
        "state",
        "group",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
    )
    search_fields = (
        "name",
        "id",
    )
    list_filter = (
        ("state", ChoicesFieldComboFilter),
        ("group", AutoCompleteFilter),
        ("created_at", DateInDateRangeFilter),
        ("updated_at", DateInDateRangeFilter),
        DjangoLookupFilter,
    )

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request: HttpRequest) -> QuerySet[DeduplicationSet]:
        return DeduplicationSet.objects.only(*self.get_list_display(request))

    @button(change_form=True)
    def clear_embeddings(self, request: HttpRequest, pk: str) -> HttpResponse:
        deduplication_set = cast("DeduplicationSet", self.get_object(request, pk))

        def _action(_: HttpRequest) -> HttpResponse:
            deduplication_set.encoding_set.update(embedding=None, embedding_status_code=None)
            deduplication_set.finding_set.all().delete()

        return confirm_action(
            modeladmin=self,
            request=request,
            action=_action,
            message="Do you confirm to clear all embeddings for this Deduplication Set?",
        )

    @button(change_form=True)
    def encode(self, request: HttpRequest, pk: str) -> HttpResponse:
        deduplication_set = cast("DeduplicationSet", self.get_object(request, pk))

        def _action(_: HttpRequest) -> HttpResponse:
            deduplication_set.encoding_set.update(embedding=None, embedding_status_code=None)
            deduplication_set.finding_set.all().delete()
            job = DedupJob.objects.create(deduplication_set=deduplication_set, encode_only=True)
            job.queue()

        return confirm_action(
            modeladmin=self,
            request=request,
            action=_action,
            message="Do you confirm to start encoding job for this Deduplication Set?",
        )

    @button(change_form=True)
    def deduplicate(self, request: HttpRequest, pk: str) -> HttpResponse:
        deduplication_set = cast("DeduplicationSet", self.get_object(request, pk))

        def _action(_: HttpRequest) -> HttpResponse:
            job = DedupJob.objects.create(deduplication_set=deduplication_set)
            job.queue()

        return confirm_action(
            modeladmin=self,
            request=request,
            action=_action,
            message="Do you confirm to start deduplication job for this Deduplication Set?",
        )

    @choice(
        label="Findings",
        change_form=True,
        change_list=False,
    )
    def findings(self, button: ChoiceButton) -> None:
        """Provide choices to Findings filtered by this Deduplication Set."""
        button.choices = [
            self.export_to_csv,
            self.findings_view,
            self.findings_remove,
        ]

    @view(label="View")
    def findings_view(self, request: HttpRequest, pk: str) -> HttpResponse:
        """Redirect to the Finding changelist filtered by Deduplication Set."""
        ds = cast("DeduplicationSet", self.get_object(request, pk))
        url = reverse("admin:api_finding_changelist", query={"deduplication_set": str(ds.pk)})
        return redirect(url)

    @view(label="Remove")
    def findings_remove(self, request: HttpRequest, pk: str) -> HttpResponse:
        """Clear all Findings for this Deduplication Set."""
        ds = cast("DeduplicationSet", self.get_object(request, pk))

        def _action(_: HttpRequest) -> HttpResponse:
            ds.finding_set.all().delete()

        return confirm_action(
            modeladmin=self,
            request=request,
            action=_action,
            message="Do you confirm to clear all findings for this Deduplication Set?",
        )

    @view(label="Export to CSV")
    def export_to_csv(self, request: HttpRequest, pk: str) -> HttpResponse:
        """Export Findings for this Deduplication Set to a CSV file."""
        deduplication_set = cast("DeduplicationSet", self.get_object(request, pk))
        queryset = deduplication_set.finding_set.all()
        return export_as_csv(
            request,
            queryset,
            filename=f"deduplication_set_{deduplication_set.pk}_findings.csv",
        )
