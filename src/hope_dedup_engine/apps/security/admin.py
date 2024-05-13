from django.contrib import admin

# from unicef_security.admin import UserAdminPlus
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from hope_dedup_engine.apps.security.models import User, UserRole


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    pass


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "system", "group")
