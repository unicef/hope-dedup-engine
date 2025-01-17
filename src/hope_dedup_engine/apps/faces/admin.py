# FYI: As of now, the shared volume for model files is mounted as read-only for Celery workers,
# which will result in an error.
# from django.conf import settings
# from django.contrib import admin

# from admin_extra_buttons.decorators import button
# from admin_extra_buttons.mixins import ExtraButtonsMixin

# from hope_dedup_engine.apps.faces.models import DummyModel


# @admin.register(DummyModel)
# class DummyModelAdmin(ExtraButtonsMixin, admin.ModelAdmin):

#     change_list_template = "admin/faces/dummymodel/change_list.html"

#     def get_queryset(self, request):
#         return DummyModel.objects.none()

#     def has_add_permission(self, request):
#         return False

#     def has_change_permission(self, request, obj=None):
#         return False

#     def has_delete_permission(self, request, obj=None):
#         return False

#     def changelist_view(self, request, extra_context=None):
#         extra_context = extra_context or {}
#         extra_context["title"] = (
#             f"Force synchronization of model weight files from GitHub to the shared volume "
#             f"at the path '{settings.DEEPFACE_WEIGHTS_BASE_LOCATION}'"
#         )
#         return super().changelist_view(request, extra_context=extra_context)

#     @button(label="Run sync")
#     def sync_models_files(self, request) -> None:
#         task = sync_model_files.delay(force=True)
#         self.message_user(
#             request,
#             f"The model files sync task `{task.id}` has started. "
#             f"The files will be forcibly synchronized with GitHub.",
#         )
