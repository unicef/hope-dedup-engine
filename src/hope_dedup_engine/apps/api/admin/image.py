from django.contrib.admin import ModelAdmin, register

from adminfilters.autocomplete import AutoCompleteFilter
from adminfilters.dates import DateRangeFilter
from adminfilters.filters import DjangoLookupFilter
from adminfilters.mixin import AdminFiltersMixin

from hope_dedup_engine.apps.api.models import Image


@register(Image)
class ImageAdmin(AdminFiltersMixin, ModelAdmin):
    list_display = (
        "id",
        "filename",
        "deduplication_set",
        "created_at",
    )

    list_filter = (
        ("deduplication_set", AutoCompleteFilter),
        ("created_at", DateRangeFilter),
        DjangoLookupFilter,
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
