from django.contrib.admin import ModelAdmin, register
from django.contrib import messages

from hope_dedup_engine.apps.api.models import HDEToken


@register(HDEToken)
class HDETokenAdmin(ModelAdmin):
    list_display = ("user",)
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:  # Only show the message when a new token is created
            self.message_user(
                request, 
                f"Token generated: {obj.key}", 
                messages.SUCCESS
            )
