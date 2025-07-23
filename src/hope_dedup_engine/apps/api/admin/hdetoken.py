from django.contrib import messages
from django.contrib.admin import ModelAdmin, register

from hope_dedup_engine.apps.api.models import HDEToken


@register(HDEToken)
class HDETokenAdmin(ModelAdmin):
    list_display = ("user",)
    fields = ("user", "key", "system")
    readonly_fields = ("key",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            self.message_user(request, f"Token generated: {obj.key}", messages.SUCCESS)
