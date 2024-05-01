from django.contrib import admin
from django.http.request import HttpRequest

from .models import TaskModel


@admin.register(TaskModel)
class TaskModelAdmin(admin.ModelAdmin):

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        return False
