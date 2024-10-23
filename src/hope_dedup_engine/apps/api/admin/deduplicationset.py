from django.contrib.admin import ModelAdmin, register
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse

from admin_extra_buttons.api import button
from admin_extra_buttons.mixins import ExtraButtonsMixin
from adminfilters.dates import DateRangeFilter
from adminfilters.filters import ChoicesFieldComboFilter, DjangoLookupFilter
from adminfilters.mixin import AdminFiltersMixin

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.utils.process import start_processing
from hope_dedup_engine.utils.security import is_root


@register(DeduplicationSet)
class DeduplicationSetAdmin(AdminFiltersMixin, ExtraButtonsMixin, ModelAdmin):
    list_display = (
        "id",
        "name",
        "reference_pk",
        "state_value",
        "created_at",
        "updated_at",
        "deleted",
    )
    readonly_fields = (
        "id",
        "state_value",
        "external_system",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
        "deleted",
    )
    search_fields = ("name",)
    list_filter = (
        ("state_value", ChoicesFieldComboFilter),
        ("created_at", DateRangeFilter),
        ("updated_at", DateRangeFilter),
        DjangoLookupFilter,
    )
    change_form_template = "admin/api/deduplicationset/change_form.html"

    def has_add_permission(self, request):
        return False

    @button(permission=is_root)
    def process(self, request: HttpRequest, pk: str) -> HttpResponseRedirect:
        dd = DeduplicationSet.objects.get(pk=pk)
        start_processing(dd)
        self.message_user(
            request,
            f"Processing for deduplication set '{dd}' has been started.",
        )
        return HttpResponseRedirect(reverse("admin:api_deduplicationset_changelist"))
