from typing import cast

from admin_extra_buttons.api import button
from admin_extra_buttons.mixins import confirm_action
from adminfilters.filters import ChoicesFieldComboFilter, DjangoLookupFilter
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
    "Release the lock only if you are sure that no task is currently running for it."
)
LOCK_RELEASED = _("Processing lock released.")
CONFIRM_MARK_FAILED = _(
    "Do you confirm to mark this set as failed? Do it only if its task is no longer running. "
    "The program's lock is released, and the client can process or cancel the set again."
)
MARKED_FAILED = _("Set marked as failed.")
MARKED_FAILED_ERROR = "Marked as failed by an administrator."

# A task owns the set in these states. If it dies, nothing moves the set on.
STUCK_STATES = (BiographicSet.State.INDEXING, BiographicSet.State.INDEXED, BiographicSet.State.DEDUPLICATING)


class ReadOnlyAdmin(BaseModelAdmin):
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False


@register(BiographicGroup)
class BiographicGroupAdmin(ReadOnlyAdmin):
    list_display = ("business_area", "program_code", "processing_locked", "deleted")
    search_fields = ("business_area", "program_code")
    list_filter = ("processing_locked", "deleted", DjangoLookupFilter)
    readonly_fields = ("business_area", "program_code", "processing_locked", "deleted", "formatted_settings")
    exclude = ("settings",)

    @display(description="Settings")
    def formatted_settings(self, obj: BiographicGroup) -> str:
        return pretty_json(obj.settings)


@register(BiographicSet)
class BiographicSetAdmin(ReadOnlyAdmin):
    list_display = ("id", "group", "state", "processing_locked", "created_at", "updated_at")
    search_fields = ("id", "group__business_area", "group__program_code")
    list_filter = (("state", ChoicesFieldComboFilter), DjangoLookupFilter)
    list_select_related = ("group",)
    readonly_fields = ("group", "state", "error", "created_at", "updated_at")

    @display(description="Processing locked", boolean=True)
    def processing_locked(self, obj: BiographicSet) -> bool:
        return obj.group.processing_locked

    @button(
        label="Unlock processing",
        change_form=True,
        change_list=False,
        permission=can.biographic.release_processing_lock,
        visible=lambda button: button.original.group.processing_locked,
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
            description=str(dataset.group),
            pk=pk,
        )

    @button(
        label="Mark as failed",
        change_form=True,
        change_list=False,
        permission=can.biographic.release_processing_lock,
        visible=lambda button: button.original.state in STUCK_STATES,
    )
    def mark_failed(self, request: HttpRequest, pk: str) -> HttpResponse:
        dataset = cast("BiographicSet", self.get_object(request, pk))

        def action(_: HttpRequest) -> HttpResponse:
            dataset.set_state(BiographicSet.State.FAILED, error=MARKED_FAILED_ERROR, force=True)
            dataset.group.release_processing_lock()
            return redirect("admin:biographic_biographicset_change", dataset.pk)

        return confirm_action(
            modeladmin=self,
            request=request,
            action=action,
            message=CONFIRM_MARK_FAILED,
            success_message=MARKED_FAILED,
            description=str(dataset),
            pk=pk,
        )


@register(BiographicRecord)
class BiographicRecordAdmin(ReadOnlyAdmin):
    list_display = ("reference_pk", "full_name", "dataset", "created_at")
    search_fields = ("full_name", "reference_pk")
    list_filter = (DjangoLookupFilter,)
    list_select_related = ("dataset",)
    readonly_fields = ("dataset", "reference_pk", "full_name", "formatted_payload", "payload_version", "created_at")
    exclude = ("payload",)

    @display(description="Payload")
    def formatted_payload(self, obj: BiographicRecord) -> str:
        return pretty_json(obj.payload)


@register(BiographicFinding)
class BiographicFindingAdmin(ReadOnlyAdmin):
    list_display = ("record", "matched_reference_pk", "matched_full_name", "scope", "score", "dataset")
    search_fields = ("record__reference_pk", "matched_reference_pk", "matched_full_name")
    list_filter = (("scope", ChoicesFieldComboFilter), DjangoLookupFilter)
    list_select_related = ("record", "dataset")
    readonly_fields = (
        "dataset",
        "record",
        "matched_reference_pk",
        "matched_full_name",
        "matched_birth_date",
        "score",
        "proximity_to_score",
        "scope",
        "formatted_config",
        "created_at",
        "updated_at",
    )
    exclude = ("config",)

    @display(description="Config")
    def formatted_config(self, obj: BiographicFinding) -> str:
        return pretty_json(obj.config)
