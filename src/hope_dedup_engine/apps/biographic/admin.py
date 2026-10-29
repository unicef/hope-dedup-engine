from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from admin_extra_buttons.api import button
from admin_extra_buttons.mixins import confirm_action
from adminfilters.autocomplete import AutoCompleteFilter, LinkedAutoCompleteFilter
from adminfilters.dates import DateInDateRangeFilter
from adminfilters.filters import ChoicesFieldComboFilter, DjangoLookupFilter, NumberFilter
from adminfilters.mixin import AdminFiltersMixin
from django.contrib import messages
from django.contrib.admin import display, register
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html_join
from django.utils.translation import gettext_lazy as _
from django_celery_boost.admin import CeleryTaskModelAdmin

from hope_dedup_engine.apps.api.admin.base import BaseModelAdmin
from hope_dedup_engine.apps.api.admin.json_display import format_log, pretty_json
from hope_dedup_engine.apps.api.utils.notification import ErrorMessage, WarningMessage, send_notification
from hope_dedup_engine.apps.biographic.config import BiographicConfig
from hope_dedup_engine.apps.biographic.exceptions import LifecycleConflictError
from hope_dedup_engine.apps.biographic.forms import BiographicGroupSettingsForm
from hope_dedup_engine.apps.biographic.models import (
    BiographicFinding,
    BiographicGroup,
    BiographicJob,
    BiographicRecord,
    BiographicSet,
)
from hope_dedup_engine.apps.biographic.services import lifecycle
from hope_dedup_engine.apps.biographic.services.status import REBUILD_STATUS
from hope_dedup_engine.apps.core.permissions import can

if TYPE_CHECKING:
    from django import forms

NOTIFICATION_SENT = _("Notification sent.")
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

CONFIRM_INDEX = _(
    "Do you confirm to index the records of this set? They are written to the program's index and the set "
    "stays indexed, waiting for a search. Nothing is scored yet."
)
CONFIRM_SEARCH = _(
    "Do you confirm to search this set against the program's index? Its findings are deleted and created again."
)
CONFIRM_REBUILD = _(
    "Do you confirm to rebuild the index from the records stored here? Approved sets are written back as approved, "
    "sets awaiting a decision as pending. Nothing is deleted from the index, so documents HOPE put in it stay."
)
QUEUED = _("Queued. Follow it in the Jobs list.")
REBUILD_QUEUED = _("Queued. The program stays locked until the rebuild finishes.")

# A task owns the set in these states. If it dies, nothing moves the set on.
STUCK_STATES = (BiographicSet.State.INDEXING, BiographicSet.State.INDEXED, BiographicSet.State.DEDUPLICATING)

# Group, then set: picking a group narrows the set choices to that group.
GROUP_AND_SET_FILTERS = (
    ("dataset__group", LinkedAutoCompleteFilter.factory(parent=None)),
    ("dataset", LinkedAutoCompleteFilter.factory(parent="dataset__group")),
)

# Name searches look inside the JSON payload too: `full_name` is the only name with
# its own column, and a client may send given and family names without it.
RECORD_NAME_SEARCH = ("full_name", "payload__given_name", "payload__family_name")


def changelist_url(model_name: str, **query: Any) -> str:
    return reverse(f"admin:biographic_{model_name}_changelist", query=query)


class ReadOnlyAdmin(BaseModelAdmin):
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False


@register(BiographicGroup)
class BiographicGroupAdmin(BaseModelAdmin):
    """A program's thresholds are edited here; the rest is read-only, as biometric does."""

    form = BiographicGroupSettingsForm
    list_display = ("business_area", "program_code", "processing_locked", "deleted")
    search_fields = ("business_area", "program_code")
    list_filter = ("processing_locked", "deleted", DjangoLookupFilter)
    readonly_fields = ("business_area", "program_code", "biographic_sets", "processing_locked", "deleted")
    fieldsets = (
        (None, {"fields": readonly_fields}),
        ("Deduplication settings", {"fields": tuple(f.name for f in BiographicConfig.setting_fields())}),
    )

    @display(description="Sets")
    def biographic_sets(self, obj: BiographicGroup) -> str:
        qs = obj.sets.only("pk", "state").order_by("created_at", "pk")
        return format_html_join(
            "\n",
            "<div><a href='{}'>{}</a> <span style='opacity:.7'>({})</span></div>",
            (
                (reverse("admin:biographic_biographicset_change", args=[ds.pk]), str(ds), ds.get_state_display())
                for ds in qs
            ),
        )

    @button(label="Records", change_form=True, change_list=False, permission=can.biographic.view_biographicrecord)
    def records(self, request: HttpRequest, pk: str) -> HttpResponse:
        return redirect(changelist_url("biographicrecord", dataset__group__exact=pk))

    @button(label="Findings", change_form=True, change_list=False, permission=can.biographic.view_biographicfinding)
    def findings(self, request: HttpRequest, pk: str) -> HttpResponse:
        return redirect(changelist_url("biographicfinding", dataset__group__exact=pk))

    @button(label="Rebuild index", change_form=True, change_list=False, permission=can.biographic.rebuild_index)
    def rebuild_index(self, request: HttpRequest, pk: str) -> HttpResponse:
        group = cast("BiographicGroup", self.get_object(request, pk))

        def action(_: HttpRequest) -> HttpResponse:
            try:
                lifecycle.start_rebuild(group)
            except LifecycleConflictError as error:
                self.message_user(request, str(error), messages.ERROR)
            else:
                self.message_user(request, REBUILD_QUEUED, messages.SUCCESS)
            return redirect("admin:biographic_biographicgroup_change", group.pk)

        return confirm_action(
            modeladmin=self, request=request, action=action, message=CONFIRM_REBUILD, description=str(group), pk=pk
        )

    def get_form(
        self, request: HttpRequest, obj: BiographicGroup | None = None, change: bool = False, **kwargs: Any
    ) -> "type[forms.ModelForm[BiographicGroup]]":
        # The threshold fields are not model fields, so the default factory would
        # reject them; the form builds them itself.
        return BiographicGroupSettingsForm

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False


@register(BiographicSet)
class BiographicSetAdmin(ReadOnlyAdmin):
    list_display = ("id", "group", "state", "processing_locked", "search_sync_pending", "created_at", "updated_at")
    search_fields = ("id", "group__business_area", "group__program_code")
    list_filter = (
        ("state", ChoicesFieldComboFilter),
        ("group", AutoCompleteFilter),
        ("created_at", DateInDateRangeFilter),
        ("updated_at", DateInDateRangeFilter),
        "search_sync_pending",
        DjangoLookupFilter,
    )
    list_select_related = ("group",)
    readonly_fields = (
        "group",
        "state",
        "error",
        "notification_url",
        "notify",
        "search_sync_pending",
        "formatted_log",
        "created_at",
        "updated_at",
    )
    exclude = ("log",)

    @display(description="Processing locked", boolean=True)
    def processing_locked(self, obj: BiographicSet) -> bool:
        return obj.group.processing_locked

    @display(description="Log")
    def formatted_log(self, obj: BiographicSet) -> str:
        return format_log(obj.log)

    @button(label="Records", change_form=True, change_list=False, permission=can.biographic.view_biographicrecord)
    def records(self, request: HttpRequest, pk: str) -> HttpResponse:
        dataset = cast("BiographicSet", self.get_object(request, pk))
        return redirect(
            changelist_url("biographicrecord", dataset__group__exact=dataset.group_id, dataset__exact=dataset.pk)
        )

    @button(label="Findings", change_form=True, change_list=False, permission=can.biographic.view_biographicfinding)
    def findings(self, request: HttpRequest, pk: str) -> HttpResponse:
        dataset = cast("BiographicSet", self.get_object(request, pk))
        return redirect(
            changelist_url("biographicfinding", dataset__group__exact=dataset.group_id, dataset__exact=dataset.pk)
        )

    @button(label="Send notification", change_form=True, change_list=False, permission=can.biographic.send_notification)
    def send_notification(self, request: HttpRequest, pk: str) -> HttpResponse:
        dataset = cast("BiographicSet", self.get_object(request, pk))
        match send_notification(dataset, force=True):
            case None:
                self.message_user(request, NOTIFICATION_SENT, messages.SUCCESS)
            case WarningMessage(message):
                self.message_user(request, message, messages.WARNING)
            case ErrorMessage(message):
                self.message_user(request, message, messages.ERROR)
        return redirect("admin:biographic_biographicset_change", dataset.pk)

    def _confirm_start(
        self,
        request: HttpRequest,
        pk: str,
        message: str,
        start: Callable[[BiographicSet], object],
        success_message: str = QUEUED,
    ) -> HttpResponse:
        """Ask for confirmation, then start `start(dataset)` and report why it could not."""
        dataset = cast("BiographicSet", self.get_object(request, pk))

        def action(_: HttpRequest) -> HttpResponse:
            try:
                start(dataset)
            except LifecycleConflictError as error:
                self.message_user(request, str(error), messages.ERROR)
            else:
                self.message_user(request, success_message, messages.SUCCESS)
            return redirect("admin:biographic_biographicset_change", dataset.pk)

        return confirm_action(
            modeladmin=self, request=request, action=action, message=message, description=str(dataset), pk=pk
        )

    @button(
        label="Index records",
        change_form=True,
        change_list=False,
        permission=can.biographic.process_indexing,
        visible=lambda button: button.original.state in BiographicSet.PROCESSABLE_STATES,
    )
    def index_records(self, request: HttpRequest, pk: str) -> HttpResponse:
        return self._confirm_start(
            request,
            pk,
            CONFIRM_INDEX,
            lambda dataset: lifecycle.start_processing(dataset, {}, BiographicJob.Mode.INDEX),
        )

    @button(
        label="Find duplicates",
        change_form=True,
        change_list=False,
        permission=can.biographic.process_deduplicate,
        visible=lambda button: button.original.state in lifecycle.SEARCHABLE_STATES,
    )
    def find_duplicates(self, request: HttpRequest, pk: str) -> HttpResponse:
        return self._confirm_start(request, pk, CONFIRM_SEARCH, lambda dataset: lifecycle.start_search(dataset, {}))

    @button(
        label="Rebuild index",
        change_form=True,
        change_list=False,
        permission=can.biographic.rebuild_index,
        visible=lambda button: button.original.state in REBUILD_STATUS,
    )
    def rebuild_index(self, request: HttpRequest, pk: str) -> HttpResponse:
        return self._confirm_start(
            request,
            pk,
            CONFIRM_REBUILD,
            lambda dataset: lifecycle.start_rebuild(dataset.group, dataset),
            REBUILD_QUEUED,
        )

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


@register(BiographicJob)
class BiographicJobAdmin(AdminFiltersMixin, CeleryTaskModelAdmin):
    """Watch and terminate runs. A job is only ever created, and queued, by `process`."""

    list_display = ("pk", "dataset_id", "progress_info", "datetime_created", "datetime_queued")
    list_filter = (
        ("dataset", AutoCompleteFilter),
        ("dataset__group", AutoCompleteFilter),
    )
    readonly_fields = ("dataset", "config_overrides")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_queue_permission(self, perm: str, request: HttpRequest, o: BiographicJob | None) -> bool:
        """Never offer the inherited "Queue" button.

        Re-queueing a job skips `start_processing`, which is what checks the set's
        state and takes the program's lock. The task would then clear the findings
        and re-index an already decided set as `pending`, and release a lock it
        never held. A run is only started through the `process` endpoint.
        """
        if perm == "queue":
            return False
        return super().has_queue_permission(perm, request, o)


@register(BiographicRecord)
class BiographicRecordAdmin(ReadOnlyAdmin):
    list_display = ("reference_pk", "full_name", "dataset", "group", "created_at")
    search_fields = ("reference_pk", *RECORD_NAME_SEARCH)
    list_filter = (*GROUP_AND_SET_FILTERS, ("created_at", DateInDateRangeFilter), DjangoLookupFilter)
    list_select_related = ("dataset__group",)
    readonly_fields = ("dataset", "reference_pk", "full_name", "formatted_payload", "payload_version", "created_at")
    exclude = ("payload",)

    @display(description="Group", ordering="dataset__group")
    def group(self, obj: BiographicRecord) -> BiographicGroup:
        return obj.dataset.group

    @display(description="Payload")
    def formatted_payload(self, obj: BiographicRecord) -> str:
        return pretty_json(obj.payload)


@register(BiographicFinding)
class BiographicFindingAdmin(ReadOnlyAdmin):
    list_display = ("record", "matched_reference_pk", "matched_full_name", "scope", "score", "dataset", "group")
    # The matched person is stored by full name only, so their given and family
    # names cannot be searched; the scored record's can.
    search_fields = (
        "record__reference_pk",
        "matched_reference_pk",
        "matched_full_name",
        *(f"record__{name}" for name in RECORD_NAME_SEARCH),
    )
    list_filter = (
        *GROUP_AND_SET_FILTERS,
        ("scope", ChoicesFieldComboFilter),
        ("score", NumberFilter),
        DjangoLookupFilter,
    )
    list_select_related = ("record", "dataset__group")
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

    @display(description="Group", ordering="dataset__group")
    def group(self, obj: BiographicFinding) -> BiographicGroup:
        return obj.dataset.group

    @display(description="Config")
    def formatted_config(self, obj: BiographicFinding) -> str:
        return pretty_json(obj.config)
