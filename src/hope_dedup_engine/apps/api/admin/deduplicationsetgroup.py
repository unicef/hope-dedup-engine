from typing import cast

from admin_extra_buttons.api import button
from admin_extra_buttons.mixins import confirm_action
from django.contrib.admin import register, display
from django.http import HttpRequest, HttpResponse
from django.utils.html import format_html_join
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from hope_dedup_engine.apps.api.admin.base import BaseModelAdmin
from hope_dedup_engine.apps.api.admin.forms import DeduplicationSetGroupSettingsForm
from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSetGroup
from hope_dedup_engine.apps.core.permissions import can

CONFIRM_RELEASE_LOCK = _(
    "Do you confirm to release the processing lock for this Deduplication Set Group? "
    "Release the lock only if you are sure that no task is currently running for this group."
)
LOCK_RELEASED = _("Processing lock released.")

CATEGORY_LABELS = {
    "detection": "Face Detection Settings",
    "recognition": "Recognition Settings",
    "quality": "Image Quality Settings",
}


def _build_fieldsets() -> tuple:
    base: list = [(None, {"fields": ("reference_pk", "name", "deduplication_sets", "processing_locked")})]
    for cat, label in CATEGORY_LABELS.items():
        fields = tuple(f.name for f in DeduplicationSetConfig.setting_fields(category=cat, admin=True))
        if fields:
            base.append((label, {"fields": fields}))
    return tuple(base)


@register(DeduplicationSetGroup)
class DeduplicationSetGroupAdmin(BaseModelAdmin):
    form = DeduplicationSetGroupSettingsForm
    readonly_fields = ("reference_pk", "name", "deduplication_sets", "processing_locked")
    search_fields = ("reference_pk", "name")
    fieldsets = _build_fieldsets()

    def get_form(self, request: HttpRequest, obj: DeduplicationSetGroup | None = None, **kwargs):
        return DeduplicationSetGroupSettingsForm

    def has_add_permission(self, request: HttpRequest) -> bool:
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

    @button(label="Encodings", change_form=True, change_list=False, permission=can.api.view_encodings)
    def encodings(self, request: HttpRequest, pk: str) -> HttpResponse:
        group = cast("DeduplicationSetGroup", self.get_object(request, pk))
        url = reverse("admin:api_encoding_changelist") + f"?deduplication_set__group__exact={group.pk}"
        return redirect(url)

    @button(label="Findings", change_form=True, change_list=False, permission=can.api.view_findings)
    def findings(self, request: HttpRequest, pk: str) -> HttpResponse:
        group = cast("DeduplicationSetGroup", self.get_object(request, pk))
        url = reverse("admin:api_finding_changelist") + f"?deduplication_set__group__exact={group.pk}"
        return redirect(url)

    @button(
        label="Unlock processing",
        change_form=True,
        change_list=False,
        permission=can.api.release_processing_lock,
        visible=lambda button: button.original.processing_locked,
    )
    def release_processing_lock(self, request: HttpRequest, pk: str) -> HttpResponse:
        group = cast("DeduplicationSetGroup", self.get_object(request, pk))

        def action(_: HttpRequest) -> HttpResponse:
            group.release_processing_lock()
            return redirect("admin:api_deduplicationsetgroup_change", group.pk)

        return confirm_action(
            modeladmin=self,
            request=request,
            action=action,
            message=CONFIRM_RELEASE_LOCK,
            success_message=LOCK_RELEASED,
            description=str(group),
            pk=pk,
        )
