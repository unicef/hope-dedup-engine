from django.contrib.admin import ModelAdmin, register

from adminfilters.filters import (
    DjangoLookupFilter,
    NumberFilter,
    RelatedFieldComboFilter,
)
from adminfilters.mixin import AdminFiltersMixin

from hope_dedup_engine.apps.api.models import Duplicate


@register(Duplicate)
class DuplicateAdmin(AdminFiltersMixin, ModelAdmin):
    list_display = (
        "id",
        "deduplication_set",
        "score",
        "first_reference_pk",
        "second_reference_pk",
    )
    list_filter = (
        ("deduplication_set", RelatedFieldComboFilter),
        ("score", NumberFilter),
        DjangoLookupFilter,
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
