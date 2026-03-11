from typing import cast

from admin_extra_buttons.api import choice, view
from admin_extra_buttons.buttons import ChoiceButton
from admin_extra_buttons.mixins import confirm_action
from django.contrib.admin import register, display
from django.http import HttpRequest, HttpResponse
from django.utils.html import format_html_join
from django.shortcuts import redirect
from django.urls import reverse

from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSetGroup
from hope_dedup_engine.apps.api.admin.base import BaseModelAdmin
from hope_dedup_engine.apps.core.permissions import can


@register(DeduplicationSetGroup)
class DeduplicationSetGroupAdmin(BaseModelAdmin):
    readonly_fields = ("reference_pk", "name", "deduplication_sets")
    fields = ("reference_pk", "name", "deduplication_sets")
    search_fields = ("reference_pk", "name")

    def has_add_permission(self, request) -> bool:
        return False

    @display(description="Deduplication Sets")
    def deduplication_sets(self, obj: DeduplicationSetGroup) -> str:
        qs = obj.deduplicationset_set.only("pk", "name", "state").order_by("updated_at", "created_at")
        return format_html_join(
            "\n",
            "<div><a href='{}'>{}</a> <span style='opacity:.7'>({})</span></div>",
            (
                (
                    reverse("admin:api_deduplicationset_change", args=[str(ds.pk)]),
                    str(ds),
                    ds.get_state_display(),
                )
                for ds in qs
            ),
        )

    @choice(label="Encodings", change_form=True, change_list=False)
    def encodings(self, button: ChoiceButton) -> None:
        """Provide choices to Encodings filtered by this DeduplicationSetGroup."""
        button.choices = [
            self.encodings_view,
            self.clear_embeddings,
        ]

    @view(label="View", permission=can.api.view_encodings)
    def encodings_view(self, request: HttpRequest, pk: str) -> HttpResponse:
        group = cast("DeduplicationSetGroup", self.get_object(request, pk))
        url = reverse("admin:api_encoding_changelist") + f"?deduplication_set__group__exact={group.pk}"
        return redirect(url)

    @view(label="Clear Embeddings", permission=can.api.clear_embeddings)
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

    @choice(label="Findings", change_form=True, change_list=False)
    def findings(self, button: ChoiceButton) -> None:
        """Provide choices to Findings filtered by this DeduplicationSetGroup."""
        button.choices = [
            self.findings_view,
            self.remove_findings,
        ]

    @view(label="View", permission=can.api.view_findings)
    def findings_view(self, request: HttpRequest, pk: str) -> HttpResponse:
        group = cast("DeduplicationSetGroup", self.get_object(request, pk))
        url = reverse("admin:api_finding_changelist") + f"?deduplication_set__group__exact={group.pk}"
        return redirect(url)

    @view(label="Remove", change_form=True, permission=can.api.remove_findings)
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
