from django.contrib.admin import ModelAdmin, register

from adminfilters.dates import DateRangeFilter
from adminfilters.filters import ChoicesFieldComboFilter, DjangoLookupFilter
from adminfilters.mixin import AdminFiltersMixin

from hope_dedup_engine.apps.api.models import DeduplicationSet


@register(DeduplicationSet)
class DeduplicationSetAdmin(AdminFiltersMixin, ModelAdmin):
    list_display = (
        "id",
        "name",
        "reference_pk",
        "state",
        "created_at",
        "updated_at",
        "deleted",
    )
    readonly_fields = (
        "id",
        "state",
        "external_system",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
        "deleted",
    )
    search_fields = ("name",)
    list_filter = (
        ("state", ChoicesFieldComboFilter),
        ("created_at", DateRangeFilter),
        ("updated_at", DateRangeFilter),
        DjangoLookupFilter,
    )

    def has_add_permission(self, request):
        return False
