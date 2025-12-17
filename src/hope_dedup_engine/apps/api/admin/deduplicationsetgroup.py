from typing import cast

from admin_extra_buttons.decorators import button
from admin_extra_buttons.mixins import ExtraButtonsMixin, confirm_action
from adminfilters.mixin import AdminFiltersMixin
from django.contrib.admin import ModelAdmin, register
from django.http import HttpRequest, HttpResponse


from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSetGroup


@register(DeduplicationSetGroup)
class DeduplicationSetGroupAdmin(ExtraButtonsMixin, AdminFiltersMixin, ModelAdmin):
    readonly_fields = ("reference_pk",)
    search_fields = ("reference_pk",)

    def has_add_permission(self, request) -> bool:
        return False

    @button(change_form=True)
    def clear_embeddings(self, request: HttpRequest, pk: str) -> HttpResponse:
        group = cast("DeduplicationSetGroup", self.get_object(request, pk))

        def _action(_: HttpRequest) -> HttpResponse:
            for deduplication_set in group.deduplicationset_set.all():
                deduplication_set.encoding_set.update(embedding=None, embedding_status_code=None)
                deduplication_set.finding_set.all().delete()

        return confirm_action(
            modeladmin=self,
            request=request,
            action=_action,
            message="Do you confirm to clear all embeddings for all Deduplication Sets in this group?",
        )

    @button(change_form=True)
    def remove_findings(self, request: HttpRequest, pk: str) -> HttpResponse:
        group = cast("DeduplicationSetGroup", self.get_object(request, pk))

        def _action(_: HttpRequest) -> HttpResponse:
            for deduplication_set in group.deduplicationset_set.all():
                deduplication_set.finding_set.all().delete()

        return confirm_action(
            modeladmin=self,
            request=request,
            action=_action,
            message="Do you confirm to remove all Findings for all Deduplication Sets in this group?",
        )
