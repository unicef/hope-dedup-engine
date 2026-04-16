from collections.abc import Callable
from typing import cast

from admin_extra_buttons.mixins import confirm_action
from admin_extra_buttons.api import button, choice, view
from admin_extra_buttons.buttons import ChoiceButton
from adminfilters.dates import DateInDateRangeFilter
from adminfilters.filters import AutoCompleteFilter, ChoicesFieldComboFilter, DjangoLookupFilter

from django.contrib import messages
from django.contrib.admin import register
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

from hope_dedup_engine.apps.api.models import DeduplicationSet, MainJob
from hope_dedup_engine.apps.api.admin.base import BaseModelAdmin
from hope_dedup_engine.apps.api.utils.notification import send_notification, WarningMessage, ErrorMessage
from hope_dedup_engine.apps.core.permissions import can
from hope_dedup_engine.apps.api.utils.export import export_as_csv


NOTIFICATION_SENT = _("Notification sent.")
ERR_GROUP_LOCKED = _("Another task is already running for this group.")
ERR_ACTIVE_SET_EXISTS = _("Cannot start job: another active set already exists in this group.")
ERR_STATE_ACTIVE_SET_EXISTS = _("Cannot change state: another active set already exists in this group.")
CONFIRM_ENCODE = _("Do you confirm to start encoding job for this Deduplication Set?")
CONFIRM_DEDUPLICATE = _("Do you confirm to start deduplication job for this Deduplication Set?")
CONFIRM_CLEAR_EMBEDDINGS = _("Do you confirm to clear all embeddings for this Deduplication Set?")
CONFIRM_REMOVE_FINDINGS = _("Do you confirm to clear all the duplicate findings for this Deduplication Set?")
WARN_FINDINGS_DELETED = _(" WARNING: {count} existing finding(s) will be deleted.")


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
        "group",
        "error",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
        "log",
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

    def _make_job_action(
        self,
        request: HttpRequest,
        deduplication_set: DeduplicationSet,
        pre_action: Callable[[], None],
        encode_only: bool = False,
    ) -> Callable[[HttpRequest], HttpResponse | None]:
        def _action(_: HttpRequest) -> HttpResponse | None:
            group = deduplication_set.group
            if not group.acquire_processing_lock():
                self.message_user(request, ERR_GROUP_LOCKED, messages.ERROR)
                return None
            try:
                with transaction.atomic():
                    pre_action()
                    deduplication_set.set_state(DeduplicationSet.State.ENCODING_IN_PROGRESS, force=True)
                    job = MainJob.objects.create(deduplication_set=deduplication_set, encode_only=encode_only)
            except IntegrityError:
                group.release_processing_lock()
                self.message_user(request, ERR_ACTIVE_SET_EXISTS, messages.ERROR)
                return None
            job.queue()

        return _action

    def _confirm_with_findings_warning(
        self,
        request: HttpRequest,
        action: Callable[[HttpRequest], HttpResponse | None],
        base_message: str,
        findings_qs: QuerySet,
    ) -> HttpResponse:
        findings_count = findings_qs.count()
        message = base_message
        if findings_count:
            message = format_lazy("{}{}", base_message, format_lazy(WARN_FINDINGS_DELETED, count=findings_count))
        return confirm_action(modeladmin=self, request=request, action=action, message=message)

    def _make_state_change_action(
        self,
        request: HttpRequest,
        deduplication_set: DeduplicationSet,
        pre_action: Callable[[], None],
        target_state: DeduplicationSet.State,
    ) -> Callable[[HttpRequest], HttpResponse | None]:
        def _action(_: HttpRequest) -> HttpResponse | None:
            try:
                with transaction.atomic():
                    pre_action()
                    deduplication_set.set_state(target_state, force=True)
            except IntegrityError:
                self.message_user(request, ERR_STATE_ACTIVE_SET_EXISTS, messages.ERROR)

        return _action

    @button(change_form=True, permission=can.api.process_encodings)
    def encode(self, request: HttpRequest, pk: str) -> HttpResponse:
        deduplication_set = cast("DeduplicationSet", self.get_object(request, pk))
        action = self._make_job_action(
            request,
            deduplication_set,
            pre_action=deduplication_set.clear_embeddings_data,
            encode_only=True,
        )
        return self._confirm_with_findings_warning(request, action, CONFIRM_ENCODE, deduplication_set.finding_set.all())

    @button(change_form=True, permission=can.api.process_deduplicate)
    def deduplicate(self, request: HttpRequest, pk: str) -> HttpResponse:
        deduplication_set = cast("DeduplicationSet", self.get_object(request, pk))
        action = self._make_job_action(
            request,
            deduplication_set,
            pre_action=lambda: deduplication_set.duplicate_findings().delete(),
        )
        return self._confirm_with_findings_warning(
            request, action, CONFIRM_DEDUPLICATE, deduplication_set.duplicate_findings()
        )

    @choice(
        label="Encodings",
        change_form=True,
        change_list=False,
    )
    def encodings(self, button: ChoiceButton) -> None:
        """Provide choices to Encodings filtered by this Deduplication Set."""
        button.choices = [
            self.encodings_view,
            self.clear_embeddings,
        ]

    @view(label="View", permission=can.api.view_encoding)
    def encodings_view(self, request: HttpRequest, pk: str) -> HttpResponse:
        """Redirect to the Encoding changelist filtered by Deduplication Set."""
        ds = cast("DeduplicationSet", self.get_object(request, pk))
        url = reverse("admin:api_encoding_changelist", query={"deduplication_set": str(ds.pk)})
        return redirect(url)

    @view(label="Clear Embeddings", permission=can.api.clear_embeddings)
    def clear_embeddings(self, request: HttpRequest, pk: str) -> HttpResponse:
        deduplication_set = cast("DeduplicationSet", self.get_object(request, pk))
        action = self._make_state_change_action(
            request,
            deduplication_set,
            pre_action=deduplication_set.clear_embeddings_data,
            target_state=DeduplicationSet.State.READY,
        )
        return self._confirm_with_findings_warning(
            request, action, CONFIRM_CLEAR_EMBEDDINGS, deduplication_set.finding_set.all()
        )

    @choice(
        label="Findings",
        change_form=True,
        change_list=False,
    )
    def findings(self, button: ChoiceButton) -> None:
        """Provide choices to Findings filtered by this Deduplication Set."""
        button.choices = [
            self.findings_export,
            self.findings_view,
            self.findings_remove,
        ]

    @button(label="Send notification", permission=can.api.send_notification)
    def send_notification(self, request: HttpRequest, pk: str) -> HttpResponse:
        obj: DeduplicationSet = self.get_object(request, pk)
        match send_notification(obj, force=True):
            case None:
                self.message_user(request, NOTIFICATION_SENT, messages.SUCCESS)
            case WarningMessage(message):
                self.message_user(request, message, messages.WARNING)
            case ErrorMessage(message):
                self.message_user(request, message, messages.ERROR)

    @view(label="View", permission=can.api.view_finding)
    def findings_view(self, request: HttpRequest, pk: str) -> HttpResponse:
        """Redirect to the Finding changelist filtered by Deduplication Set."""
        ds = cast("DeduplicationSet", self.get_object(request, pk))
        url = reverse("admin:api_finding_changelist", query={"deduplication_set": str(ds.pk)})
        return redirect(url)

    @view(label="Remove", permission=can.api.remove_findings)
    def findings_remove(self, request: HttpRequest, pk: str) -> HttpResponse:
        """Clear all Findings for this Deduplication Set."""
        deduplication_set = cast("DeduplicationSet", self.get_object(request, pk))
        action = self._make_state_change_action(
            request,
            deduplication_set,
            pre_action=lambda: deduplication_set.duplicate_findings().delete(),
            target_state=DeduplicationSet.State.ENCODED,
        )
        return self._confirm_with_findings_warning(
            request, action, CONFIRM_REMOVE_FINDINGS, deduplication_set.duplicate_findings()
        )

    @view(label="Export to CSV", permission=can.api.export_findings)
    def findings_export(self, request: HttpRequest, pk: str) -> StreamingHttpResponse:
        """Export Findings for this Deduplication Set to a CSV file."""
        deduplication_set = cast("DeduplicationSet", self.get_object(request, pk))
        qs = deduplication_set.finding_set.all()
        filename = f"deduplication_set_{deduplication_set}_findings.csv"
        return export_as_csv(qs, filename)
