from django.contrib import admin

from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from hope_dedup_engine.apps.security.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    pass
