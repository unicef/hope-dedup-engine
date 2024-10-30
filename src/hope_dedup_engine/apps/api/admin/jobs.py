from django.contrib import admin

from django_celery_boost.admin import CeleryTaskModelAdmin

from hope_dedup_engine.apps.api.models.jobs import DedupJob


@admin.register(DedupJob)
class AsyncJobAdmin(CeleryTaskModelAdmin):
    pass
