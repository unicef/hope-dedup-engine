from adminfilters.autocomplete import AutoCompleteFilter
from adminfilters.mixin import AdminFiltersMixin
from django.contrib import admin
from django_celery_boost.admin import CeleryTaskModelAdmin

from hope_dedup_engine.apps.api.models.jobs import (
    DedupJob,
    SyncDnnFilesJob,
)


@admin.register(DedupJob)
class DedupJobAdmin(AdminFiltersMixin, CeleryTaskModelAdmin):
    list_display = ["pk", "deduplication_set_id", "datetime_created", "datetime_queued"]
    list_filter = (
        ("deduplication_set", AutoCompleteFilter),
        ("deduplication_set__group", AutoCompleteFilter),
    )


@admin.register(SyncDnnFilesJob)
class SyncDnnFilesJobAdmin(CeleryTaskModelAdmin):
    list_display = ["pk", "datetime_created", "datetime_queued"]
