from django.contrib import admin

from hope_dedup_engine.apps.api.models import (
    DeduplicationSet,
    Duplicate,
    HDEToken,
    Image,
)

admin.site.register(DeduplicationSet)
admin.site.register(Duplicate)
admin.site.register(HDEToken)
admin.site.register(Image)
