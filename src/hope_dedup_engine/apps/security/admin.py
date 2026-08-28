from django.contrib.admin import register

from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from hope_dedup_engine.apps.security.models import User


@register(User)
class UserAdmin(BaseUserAdmin):
    pass
