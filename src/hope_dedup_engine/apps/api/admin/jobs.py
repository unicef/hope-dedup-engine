from django.contrib import admin

from django_celery_boost.admin import CeleryTaskModelAdmin

from hope_dedup_engine.apps.api.models.jobs import DedupJob

from .base import DeduplicationSetLightQuerysetMixin


@admin.register(DedupJob)
class DedupJobAdmin(DeduplicationSetLightQuerysetMixin, CeleryTaskModelAdmin):
    list_display = ["deduplication_set_id", "progress"]
