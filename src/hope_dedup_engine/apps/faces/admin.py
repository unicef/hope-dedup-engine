from django.contrib import admin

from admin_extra_buttons.decorators import button
from admin_extra_buttons.mixins import ExtraButtonsMixin
from celery import group
from constance import config

from hope_dedup_engine.apps.faces.celery_tasks import sync_dnn_files
from hope_dedup_engine.apps.faces.models import DummyModel
from hope_dedup_engine.config.celery import app as celery_app


@admin.register(DummyModel)
class DummyModelAdmin(ExtraButtonsMixin, admin.ModelAdmin):

    change_list_template = "admin/faces/dummymodel/change_list.html"

    def get_queryset(self, request):
        return DummyModel.objects.none()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["title"] = (
            f"Force syncronize DNN files from {config.DNN_FILES_SOURCE} to local storage."
        )
        return super().changelist_view(request, extra_context=extra_context)

    @button(label="Run sync")
    def sync_dnn_files(self, request):
        active_workers = celery_app.control.inspect().active_queues()
        if not active_workers:
            self.message_user(
                request,
                "No active workers found. Please start the Celery worker processes.",
            )
        else:
            worker_count = len(active_workers)
            if worker_count > 1:
                job = group(sync_dnn_files.s(force=True) for _ in range(worker_count))
                result = job.apply_async()
                self.message_user(
                    request,
                    f"The DNN files synchronization group task `{result.id}` has been initiated across "
                    f"`{worker_count}` workers. "
                    f"The files will be forcibly synchronized with `{config.DNN_FILES_SOURCE}`.",
                )
            else:
                task = sync_dnn_files.delay(force=True)
                self.message_user(
                    request,
                    f"The DNN files sync task `{task.id}` has started. "
                    f"The files will be forcibly synchronized with `{config.DNN_FILES_SOURCE}`.",
                )

        return None
