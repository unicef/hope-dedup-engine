from typing import cast

from admin_extra_buttons.decorators import button, link
from admin_extra_buttons.mixins import ExtraButtonsMixin, confirm_action
from adminfilters.dates import DateInDateRangeFilter
from adminfilters.filters import ChoicesFieldComboFilter, DjangoLookupFilter
from adminfilters.mixin import AdminFiltersMixin
from django.contrib.admin import ModelAdmin, register
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from rest_framework.reverse import reverse

from hope_dedup_engine.apps.api.models import DeduplicationSet, DedupJob


@register(DeduplicationSet)
class DeduplicationSetAdmin(ExtraButtonsMixin, AdminFiltersMixin, ModelAdmin):
    list_display = (
        "id",
        "name",
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
        "reference_pk",
    )
    list_filter = (
        ("state", ChoicesFieldComboFilter),
        ("created_at", DateInDateRangeFilter),
        ("updated_at", DateInDateRangeFilter),
        DjangoLookupFilter,
    )

    def has_add_permission(self, request):
        return False

    @link()
    def findings(self, button: button) -> str | None:
        if "original" in button.context:
            obj = button.context["original"]
            url = reverse("admin:api_finding_changelist")
            button.href = f"{url}?deduplication_set={obj.pk}"
            button.visible = True
        else:
            button.visible = False
        return None

    def get_queryset(self, request: HttpRequest) -> QuerySet[DeduplicationSet]:
        return DeduplicationSet.objects.only(*self.get_list_display(request))

    @button(change_form=True)
    def clear_embeddings(self, request: HttpRequest, pk: str) -> HttpResponse | HttpResponseRedirect:
        if request.method == "POST":
            deduplication_set = cast("DeduplicationSet", self.get_object(request, pk))
            deduplication_set.encoding_set.update(embedding=None, embedding_status_code=None)
            deduplication_set.finding_set.all().delete()
            return HttpResponseRedirect(reverse("admin:api_deduplicationset_change", args=[pk]))
        return confirm_action(
            modeladmin=self,
            request=request,
            action=self.clear_embeddings,
            message="Do you confirm to clear all embeddings for this Deduplication Set?",
        )

    @button(change_form=True)
    def remove_findings(self, request: HttpRequest, pk: str) -> HttpResponse | HttpResponseRedirect:
        if request.method == "POST":
            deduplication_set = cast("DeduplicationSet", self.get_object(request, pk))
            deduplication_set.finding_set.all().delete()
            return HttpResponseRedirect(reverse("admin:api_deduplicationset_change", args=[pk]))
        return confirm_action(
            modeladmin=self,
            request=request,
            action=self.remove_findings,
            message="Do you confirm to clear all findings for this Deduplication Set?",
        )

    @button(change_form=True)
    def encode(self, request: HttpRequest, pk: str) -> HttpResponse | HttpResponseRedirect:
        if request.method == "POST":
            deduplication_set = cast("DeduplicationSet", self.get_object(request, pk))
            deduplication_set.encoding_set.update(embedding=None, embedding_status_code=None)
            deduplication_set.finding_set.all().delete()
            job = DedupJob.objects.create(deduplication_set=deduplication_set, encode_only=True)
            job.queue()
            return HttpResponseRedirect(reverse("admin:api_deduplicationset_change", args=[pk]))
        return confirm_action(
            modeladmin=self,
            request=request,
            action=self.encode,
            message="Do you confirm to start encoding job for this Deduplication Set?",
        )

    @button(change_form=True)
    def deduplicate(self, request: HttpRequest, pk: str) -> HttpResponse | HttpResponseRedirect:
        if request.method == "POST":
            deduplication_set = cast("DeduplicationSet", self.get_object(request, pk))
            job = DedupJob.objects.create(deduplication_set=deduplication_set)
            job.queue()
            return HttpResponseRedirect(reverse("admin:api_deduplicationset_change", args=[pk]))
        return confirm_action(
            modeladmin=self,
            request=request,
            action=self.deduplicate,
            message="Do you confirm to start deduplication job for this Deduplication Set?",
        )
