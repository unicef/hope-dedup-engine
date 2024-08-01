from django.contrib import admin

from admin_extra_buttons.decorators import button
from admin_extra_buttons.mixins import ExtraButtonsMixin
from constance import config

from hope_dedup_engine.apps.faces.celery_tasks import sync_dnn_files
from hope_dedup_engine.apps.faces.models import DummyModel


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
        task = sync_dnn_files.delay(force=True)
        self.message_user(
            request,
            f"DNN files sync task {task.id} has started. The files will be forced to sync with {config.DNN_FILES_SOURCE}.",  # noqa: E501
        )
        return None
