from django.contrib.admin import ModelAdmin, register

from adminfilters.autocomplete import AutoCompleteFilter
from adminfilters.filters import DjangoLookupFilter, NumberFilter
from adminfilters.mixin import AdminFiltersMixin

from hope_dedup_engine.apps.api.models import Finding


@register(Finding)
class FindingAdmin(AdminFiltersMixin, ModelAdmin):
    list_display = (
        "id",
        "deduplication_set",
        "score",
        "error",
        "first_reference_pk",
        "second_reference_pk",
    )
    list_filter = (
        ("deduplication_set", AutoCompleteFilter),
        ("score", NumberFilter),
        ("error", NumberFilter),
        DjangoLookupFilter,
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return obj is not None
