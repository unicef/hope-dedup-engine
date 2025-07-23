from django.contrib.auth.models import Group

import factory

from hope_dedup_engine.apps.security.models import System, User, UserRole

from .base import AutoRegisterModelFactory


class SystemFactory(AutoRegisterModelFactory):
    name = factory.fuzzy.FuzzyText()

    class Meta:
        model = System


class UserFactory(AutoRegisterModelFactory):
    _password = "password"
    username = factory.Sequence(lambda n: "m%03d@example.com" % n)
    password = factory.django.Password(_password)
    email = factory.Sequence(lambda n: "m%03d@example.com" % n)

    class Meta:
        model = User
        django_get_or_create = ("username",)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        ret = super()._create(model_class, *args, **kwargs)
        ret._password = cls._password
        return ret

    @factory.post_generation
    def groups(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for group in extracted:
                self.groups.add(group)
        else:
            self.groups.add(Group.objects.get(name="API users"))


class SuperUserFactory(UserFactory):
    username = factory.Sequence(lambda n: "superuser%03d@example.com" % n)
    email = factory.Sequence(lambda n: "superuser%03d@example.com" % n)
    is_superuser = True
    is_staff = True
    is_active = True


class GroupFactory(AutoRegisterModelFactory):
    name = factory.Sequence(lambda n: "Group-%03d" % n)

    class Meta:
        model = Group
        django_get_or_create = ("name",)


class UserRoleFactory(AutoRegisterModelFactory):
    user = factory.SubFactory(UserFactory)
    group = factory.SubFactory(GroupFactory)
    system = factory.SubFactory(SystemFactory)

    class Meta:
        model = UserRole
