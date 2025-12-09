from typing import cast

from admin_extra_buttons.decorators import button
from admin_extra_buttons.mixins import ExtraButtonsMixin
from adminfilters.mixin import AdminFiltersMixin
from django.contrib import messages
from django.contrib.admin import ModelAdmin, register
from django.http import HttpRequest

from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSetGroup


@register(DeduplicationSetGroup)
class DeduplicationSetGroupAdmin(ExtraButtonsMixin, AdminFiltersMixin, ModelAdmin):
    readonly_fields = ("reference_pk",)
    search_fields = ("reference_pk",)

    def has_add_permission(self, request) -> bool:
        return False

    @button(change_form=True)
    def reset_encodings(self, request: HttpRequest, pk: str) -> None:
        group = cast("DeduplicationSetGroup", self.get_object(request, pk))
        for deduplication_set in group.deduplicationset_set.all():
            deduplication_set.encoding_set.update(embedding=None, embedding_status_code=None)
        self.message_user(request, "Encodings reset.", level=messages.SUCCESS)

    @button(change_form=True)
    def remove_findings(self, request: HttpRequest, pk: str) -> None:
        group = cast("DeduplicationSetGroup", self.get_object(request, pk))
        for deduplication_set in group.deduplicationset_set.all():
            deduplication_set.finding_set.all().delete()
        self.message_user(request, "Findings removed.", level=messages.SUCCESS)
