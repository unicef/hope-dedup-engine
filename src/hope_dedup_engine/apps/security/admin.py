from django.contrib import admin

# from unicef_security.admin import UserAdminPlus
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from hope_dedup_engine.apps.security.models import ExternalSystem, User, UserRole


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + ((None, {"fields": ("external_system",)}),)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "system", "group")


@admin.register(ExternalSystem)
class ExternalSystemAdmin(admin.ModelAdmin):
    pass
