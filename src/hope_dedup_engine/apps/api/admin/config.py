from django.contrib.admin import ModelAdmin, register

from hope_dedup_engine.apps.api.models import Config


@register(Config)
class ConfigAdmin(ModelAdmin):
    pass
