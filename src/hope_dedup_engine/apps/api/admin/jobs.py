from django.contrib import admin

from django_celery_boost.admin import CeleryTaskModelAdmin

from hope_dedup_engine.apps.api.models.jobs import DedupJob


@admin.register(DedupJob)
class DedupJobAdmin(CeleryTaskModelAdmin):
    list_display = ["deduplication_set_id", "progress"]
