from adminfilters.autocomplete import AutoCompleteFilter
from adminfilters.mixin import AdminFiltersMixin
from django.contrib import admin

from django_celery_boost.admin import CeleryTaskModelAdmin

from hope_dedup_engine.apps.api.models.jobs import (
    DedupJob,
    EncodeChunkJob,
    DedupeChunkJob,
    CallbackFindingsJob,
    DeduplicateDatasetJob,
    SyncDnnFilesJob,
)


class DeduplicationSetRelatedJobAdminMixin(AdminFiltersMixin):
    list_display = ["pk", "deduplication_set_id", "datetime_created", "datetime_queued"]
    list_filter = (
        ("deduplication_set", AutoCompleteFilter),
        ("deduplication_set__group", AutoCompleteFilter),
    )


@admin.register(DedupJob)
class DedupJobAdmin(DeduplicationSetRelatedJobAdminMixin, CeleryTaskModelAdmin):
    pass


@admin.register(EncodeChunkJob)
class EncodeChunkJobAdmin(DeduplicationSetRelatedJobAdminMixin, CeleryTaskModelAdmin):
    pass


@admin.register(DedupeChunkJob)
class DedupeChunkJobAdmin(DeduplicationSetRelatedJobAdminMixin, CeleryTaskModelAdmin):
    pass


@admin.register(CallbackFindingsJob)
class CallbackFindingsJobAdmin(DeduplicationSetRelatedJobAdminMixin, CeleryTaskModelAdmin):
    pass


@admin.register(DeduplicateDatasetJob)
class DeduplicateDatasetJobAdmin(DeduplicationSetRelatedJobAdminMixin, CeleryTaskModelAdmin):
    pass


@admin.register(SyncDnnFilesJob)
class SyncDnnFilesJobAdmin(CeleryTaskModelAdmin):
    list_display = ["pk", "datetime_created", "datetime_queued"]
