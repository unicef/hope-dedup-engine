from django.contrib import messages
from django.contrib.admin import ModelAdmin, register

from admin_extra_buttons.decorators import button, link
from admin_extra_buttons.mixins import ExtraButtonsMixin
from adminfilters.dates import DateRangeFilter
from adminfilters.filters import ChoicesFieldComboFilter, DjangoLookupFilter
from adminfilters.mixin import AdminFiltersMixin
from django.db.models import QuerySet
from django.http import HttpRequest
from rest_framework.reverse import reverse
from django.utils.translation import gettext as _
from hope_dedup_engine.apps.api.models import DeduplicationSet


@register(DeduplicationSet)
class DeduplicationSetAdmin(ExtraButtonsMixin, AdminFiltersMixin, ModelAdmin):
    list_display = (
        "id",
        "name",
        "reference_pk",
        "state",
        "config",
        "created_at",
        "updated_at",
        "deleted",
    )
    readonly_fields = (
        "id",
        "state",
        "system",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
        "deleted",
    )
    search_fields = ("name", "id")
    list_filter = (
        ("state", ChoicesFieldComboFilter),
        ("created_at", DateRangeFilter),
        ("updated_at", DateRangeFilter),
        DjangoLookupFilter,
    )

    def has_add_permission(self, request):
        return False

    @link()
    def findings(self, button: button) -> str | None:
        if "original" in button.context:
            obj = button.context["original"]
            url = reverse("admin:api_finding_changelist")
            button.href = f"{url}?deduplication_set={obj.pk}"
            button.visible = True
        else:
            button.visible = False
        return None

    @button(
        label="Terminate Job",
        permission=lambda request, obj, **kwargs: (
            request.user.is_staff
            and obj
            and obj.state not in [DeduplicationSet.State.FAILED, DeduplicationSet.State.CANCELED]
        ),
        confirm=_("Are you sure you want to terminate the running job for this deduplication set?"),
    )
    def terminate_job(self, request: HttpRequest, pk: str) -> None:
        ds = self.get_object(request, pk)

        job = getattr(ds, "dedupjob", None)

        if job and job.curr_async_result_id:
            new_status = job.terminate()
            self.message_user(
                request,
                f"Job termination initiated. New job status: {new_status}.",
                messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                _("No active job found. Setting state to Canceled."),
                messages.WARNING,
            )
        ds.set_state(DeduplicationSet.State.CANCELED)

    def get_queryset(self, request: HttpRequest) -> QuerySet[DeduplicationSet]:
        return DeduplicationSet.objects.only(*self.get_list_display(request))
