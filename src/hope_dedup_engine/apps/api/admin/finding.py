from django.contrib.admin import ModelAdmin, register
from uuid import uuid4
from django.contrib import admin

from adminfilters.autocomplete import AutoCompleteFilter
from adminfilters.filters import DjangoLookupFilter, NumberFilter
from adminfilters.mixin import AdminFiltersMixin

from hope_dedup_engine.apps.api.models import Finding, Image, Config

from .base import DeduplicationSetLightQuerysetMixin


@register(Finding)
class FindingAdmin(AdminFiltersMixin, DeduplicationSetLightQuerysetMixin, ModelAdmin):
    list_display = (
        "id",
        "deduplication_set",
        "score",
        "first_reference_pk",
        "second_reference_pk",
        "formatted_status_code",
        "created_at",
        "updated_at",
    )

    def formatted_status_code(self, obj):
        return f"{obj.status_code} {Image.StatusCode(obj.status_code).name}"

    formatted_status_code.short_description = "Status Code"

    list_filter = (
        ("deduplication_set", AutoCompleteFilter),
        ("score", NumberFilter),
        DjangoLookupFilter,
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return obj is not None


@admin.register(Config)
class ConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "settings", "created_at")
    fields = ("name", "settings", "root_token")
    readonly_fields = ("created_at",)

    def save_model(self, request, obj, form, change):
        if not obj.root_token:
            obj.root_token = uuid4().hex  
        super().save_model(request, obj, form, change)
