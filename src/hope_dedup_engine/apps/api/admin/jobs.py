from adminfilters.autocomplete import AutoCompleteFilter
from adminfilters.mixin import AdminFiltersMixin
from django.contrib import admin

from django_celery_boost.admin import CeleryTaskModelAdmin

from hope_dedup_engine.apps.api.models.jobs import DedupJob


@admin.register(DedupJob)
class DedupJobAdmin(AdminFiltersMixin, CeleryTaskModelAdmin):
    list_display = ["deduplication_set_id", "progress"]
    list_filter = (
        ("deduplication_set_id__group", AutoCompleteFilter),
        ("deduplication_set_id", AutoCompleteFilter),
    )
