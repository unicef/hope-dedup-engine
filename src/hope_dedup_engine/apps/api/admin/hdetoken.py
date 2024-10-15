from django.contrib.admin import ModelAdmin, register

from hope_dedup_engine.apps.api.models import HDEToken


@register(HDEToken)
class HDETokenAdmin(ModelAdmin):
    pass
