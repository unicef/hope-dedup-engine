import json
from typing import Any

from django.contrib import messages
from django.contrib.admin import ModelAdmin, register, site
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse

from admin_extra_buttons.api import button
from admin_extra_buttons.mixins import ExtraButtonsMixin
from django_svelte_jsoneditor.widgets import SvelteJSONEditorWidget

from hope_dedup_engine.apps.api.forms import EditSchemaForm
from hope_dedup_engine.apps.api.models import Config, DeduplicationSet
from hope_dedup_engine.apps.api.utils.notification import send_notification
from hope_dedup_engine.apps.api.utils.shema_manager import SchemaManager
from hope_dedup_engine.apps.api.validators import DefaultValidatingValidator
from hope_dedup_engine.utils.security import is_root


@register(Config)
class ConfigAdmin(ExtraButtonsMixin, ModelAdmin):
    list_display = ("name", "settings")
    change_list_template = "admin/api/config/change_list.html"

    formfield_overrides = {
        models.JSONField: {
            "widget": SvelteJSONEditorWidget,
        }
    }

    def get_changeform_initial_data(self, request: HttpRequest) -> dict[str, str]:
        initial_data = super().get_changeform_initial_data(request)
        initial_data["settings"] = {}
        try:
            schema = SchemaManager.get_or_create()
            DefaultValidatingValidator(schema).validate(initial_data["settings"])
        except ValidationError as e:
            self.message_user(request, e.message, level=messages.ERROR)
        return initial_data

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "confirm-save/<int:object_id>/",
                self.admin_site.admin_view(self.confirm_save),
                name="confirm_save_config",
            ),
            path(
                "change-settings-schema/",
                self.admin_site.admin_view(self.change_settings_schema),
                name="change_settings_schema",
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
                f"Related deduplication sets {dd_set} was found. "
                f"Confirming your save will mark them as '{DeduplicationSet.State.DIRTY.label}'.",
                level=messages.WARNING,
            )
            return redirect(confirm_url)
        return super().response_change(request, obj)

    def confirm_save(self, request, object_id) -> HttpResponse:  # pragma: no cover
        obj = self.get_object(request, object_id)
        if request.method == "POST":
            form_data = request.session.get("unsaved_data", None)

            if form_data:
                with transaction.atomic():
                    deduplication_sets = obj.deduplicationset_set.select_for_update()
                    deduplication_sets.update(state=DeduplicationSet.State.DIRTY)
                    for ds in deduplication_sets:
                        send_notification(ds.notification_url)
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

    @button(permission=is_root)
    def change_settings_schema(
        self, request: HttpRequest
    ) -> HttpResponse:  # pragma: no cover
        context = {
            "opts": self.model._meta,
            "site_header": site.site_header,
            "title": "Change settings shema",
            "trail_label": "Settings schema",
            "has_view_permission": self.has_view_permission(request),
        }

        if request.method == "POST":
            form = EditSchemaForm(request.POST)
            if form.is_valid():
                try:
                    SchemaManager.save(form.cleaned_data["schema"])
                except ValidationError as e:
                    self.message_user(request, e.message, level=messages.ERROR)
                else:
                    self.message_user(request, "Schema has been updated.")
                    return redirect(reverse("admin:api_config_changelist"))
        else:
            try:
                form = EditSchemaForm(initial={"schema": SchemaManager.get_or_create()})
            except ValidationError as e:
                self.message_user(request, e.message, level=messages.ERROR)
                return redirect(reverse("admin:api_config_changelist"))

        return render(
            request,
            "admin/api/config/change_settings_schema.html",
            {
                "form": form,
                **context,
            },
        )
