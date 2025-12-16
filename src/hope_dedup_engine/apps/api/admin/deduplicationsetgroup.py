from typing import cast

from admin_extra_buttons.decorators import button
from admin_extra_buttons.mixins import ExtraButtonsMixin, confirm_action
from adminfilters.mixin import AdminFiltersMixin
from django.contrib.admin import ModelAdmin, register
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse


from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSetGroup


@register(DeduplicationSetGroup)
class DeduplicationSetGroupAdmin(ExtraButtonsMixin, AdminFiltersMixin, ModelAdmin):
    readonly_fields = ("reference_pk",)
    search_fields = ("reference_pk",)

    def has_add_permission(self, request) -> bool:
        return False

    @button(change_form=True)
    def clear_embeddings(self, request: HttpRequest, pk: str) -> HttpResponse | HttpResponseRedirect:
        if request.method == "POST":
            group = cast("DeduplicationSetGroup", self.get_object(request, pk))
            for deduplication_set in group.deduplicationset_set.all():
                deduplication_set.encoding_set.update(embedding=None, embedding_status_code=None)
                deduplication_set.finding_set.all().delete()
            return HttpResponseRedirect(reverse("admin:api_deduplicationsetgroup_change", args=[pk]))
        return confirm_action(
            modeladmin=self,
            request=request,
            action=self.clear_embeddings,
            message="Do you confirm to clear all embeddings for all Deduplication Sets in this group?",
        )

    @button(change_form=True)
    def remove_findings(self, request: HttpRequest, pk: str) -> HttpResponse | HttpResponseRedirect:
        if request.method == "POST":
            group = cast("DeduplicationSetGroup", self.get_object(request, pk))
            for deduplication_set in group.deduplicationset_set.all():
                deduplication_set.finding_set.all().delete()
            return HttpResponseRedirect(reverse("admin:api_deduplicationsetgroup_change", args=[pk]))
        return confirm_action(
            modeladmin=self,
            request=request,
            action=self.remove_findings,
            message="Do you confirm to remove all Findings for all Deduplication Sets in this group?",
        )
