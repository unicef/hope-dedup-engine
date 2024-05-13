import factory

from hope_dedup_engine.apps.security.models import UserRole

from .base import AutoRegisterModelFactory
from .django_auth import GroupFactory
from .system import SystemFactory
from .user import UserFactory


class UserRoleFactory(AutoRegisterModelFactory):
    class Meta:
        model = UserRole
        django_get_or_create = ("user", "group", "system")

    user = factory.SubFactory(UserFactory)
    group = factory.SubFactory(GroupFactory)
    system = factory.SubFactory(SystemFactory)
