from typing import cast

from admin_extra_buttons.api import button
from admin_extra_buttons.mixins import confirm_action
from adminfilters.filters import DjangoLookupFilter
from django.contrib.admin import display, register
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

from hope_dedup_engine.apps.api.admin.base import BaseModelAdmin
from hope_dedup_engine.apps.api.admin.json_display import pretty_json
from hope_dedup_engine.apps.biographic.models import (
    BiographicFinding,
    BiographicGroup,
    BiographicRecord,
    BiographicSet,
)
from hope_dedup_engine.apps.core.permissions import can

CONFIRM_RELEASE_LOCK = _(
    "Do you confirm to release the processing lock for this program? "
    "Release the lock only if you are sure that no task is currently running."
)
LOCK_RELEASED = _("Processing lock released.")


@register(BiographicGroup)
class BiographicGroupAdmin(BaseModelAdmin):
    list_display = ("business_area", "program_id", "name", "processing_locked", "deleted")
    readonly_fields = ("business_area", "program_id", "processing_locked", "deleted")
    search_fields = ("business_area", "program_id", "name")
    list_filter = ("processing_locked", "deleted", DjangoLookupFilter)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False


@register(BiographicSet)
class BiographicSetAdmin(BaseModelAdmin):
    list_display = ("id", "group", "state", "processing_locked")
    readonly_fields = ("group", "state", "processing_locked")
    search_fields = ("id", "group__business_area", "group__program_id")
    list_filter = ("state", DjangoLookupFilter)
    list_select_related = ("group",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    @display(description="Processing locked", boolean=True)
    def processing_locked(self, obj: BiographicSet) -> bool:
        return obj.group.processing_locked

    @button(
        label="Unlock processing",
        change_form=True,
        change_list=False,
        permission=can.biographic.release_processing_lock,
        visible=lambda button: bool(button.original and button.original.group.processing_locked),
    )
    def release_processing_lock(self, request: HttpRequest, pk: str) -> HttpResponse:
        dataset = cast("BiographicSet", self.get_object(request, pk))

        def action(_: HttpRequest) -> HttpResponse:
            dataset.group.release_processing_lock()
            return redirect("admin:biographic_biographicset_change", dataset.pk)

        return confirm_action(
            modeladmin=self,
            request=request,
            action=action,
            message=CONFIRM_RELEASE_LOCK,
            success_message=LOCK_RELEASED,
            description=str(dataset),
            pk=pk,
        )


@register(BiographicRecord)
class BiographicRecordAdmin(BaseModelAdmin):
    list_display = ("reference_pk", "full_name", "dataset", "created_at")
    readonly_fields = ("dataset", "reference_pk", "full_name", "payload_version", "created_at", "formatted_payload")
    exclude = ("payload",)
    search_fields = ("full_name", "reference_pk")
    list_select_related = ("dataset", "dataset__group")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    @display(description="Payload")
    def formatted_payload(self, obj: BiographicRecord) -> str:
        return pretty_json(obj.payload)


@register(BiographicFinding)
class BiographicFindingAdmin(BaseModelAdmin):
    list_display = ("id", "record", "matched_reference_pk", "score", "status_code", "scope")
    readonly_fields = (
        "record",
        "matched_reference_pk",
        "score",
        "proximity_to_score",
        "status_code",
        "scope",
        "config",
        "updated_at",
    )
    search_fields = ("matched_reference_pk", "record__reference_pk")
    list_filter = ("status_code", "scope", DjangoLookupFilter)
    list_select_related = ("record",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
