from typing import cast

from admin_extra_buttons.decorators import button
from admin_extra_buttons.mixins import confirm_action
from django.contrib.admin import register
from django.http import HttpRequest, HttpResponse

from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSetGroup
from hope_dedup_engine.apps.api.admin.base import BaseModelAdmin
from hope_dedup_engine.apps.core.permissions import can


@register(DeduplicationSetGroup)
class DeduplicationSetGroupAdmin(BaseModelAdmin):
    readonly_fields = ("reference_pk", "name")
    search_fields = ("reference_pk", "name")

    def has_add_permission(self, request) -> bool:
        return False

    @button(change_form=True, permission=can.api.clear_embeddings)
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

    @button(change_form=True, permission=can.api.remove_findings)
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
