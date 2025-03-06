from django.contrib import admin

from adminfilters.autocomplete import AutoCompleteFilter
from adminfilters.mixin import AdminFiltersMixin

from hope_dedup_engine.apps.api.models import (
    IgnoredFilenamePair,
    IgnoredReferencePkPair,
)

from .base import DeduplicationSetLightQuerysetMixin


class IgnoredPairBaseAdmin(AdminFiltersMixin, DeduplicationSetLightQuerysetMixin, admin.ModelAdmin):
    list_display = ("id", "first", "second", "deduplication_set")
    list_filter = (("deduplication_set", AutoCompleteFilter),)
    search_fields = ("first", "second")


@admin.register(IgnoredReferencePkPair)
class IgnoredReferencePkPairAdmin(IgnoredPairBaseAdmin):
    pass


@admin.register(IgnoredFilenamePair)
class IgnoredFilenamePairAdmin(IgnoredPairBaseAdmin):
    pass
