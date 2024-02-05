from django.contrib import admin

from unicef_security.admin import UserAdminPlus

from hope_dedup_engine.apps.core.models import User


@admin.register(User)
class UserAdminPlus(UserAdminPlus):
    pass
