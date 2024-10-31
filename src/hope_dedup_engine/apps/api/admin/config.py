import json
from typing import Any

from django.contrib import messages
from django.contrib.admin import ModelAdmin, register
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse

from hope_dedup_engine.apps.api.models import Config


@register(Config)
class ConfigAdmin(ModelAdmin):
    list_display = ("name", "settings")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "confirm-save/<int:object_id>/",
                self.admin_site.admin_view(self.confirm_save),
                name="confirm_save_config",
            ),
        ]
        return custom_urls + urls

    def response_change(self, request: HttpRequest, obj: Any) -> HttpResponse:
        dd_set = ", ".join([str(d) for d in obj.deduplicationset_set.all()])
        if dd_set:
            request.session["unsaved_data"] = request.POST.dict()
            confirm_url = reverse("admin:confirm_save_config", args=[obj.pk])
            self.message_user(
                request,
                f"Related deduplication sets {dd_set} was found. Please confirm saving.",
                level=messages.WARNING,
            )
            return redirect(confirm_url)
        return super().response_change(request, obj)

    def confirm_save(self, request, object_id):  # pragma: no cover
        obj = self.get_object(request, object_id)
        if request.method == "POST":
            form_data = request.session.get("unsaved_data", None)
            if form_data:
                for field, value in form_data.items():
                    if field == "settings":
                        value = json.loads(value)
                    setattr(obj, field, value)
                obj.save()

            return redirect(reverse("admin:api_config_changelist"))

        return render(
            request,
            "admin/api/config/confirm_save.html",
            {
                "object": obj,
                "form_data": request.session.get("unsaved_data"),
            },
        )
