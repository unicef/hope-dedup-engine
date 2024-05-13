import factory
from testutils.factories.base import AutoRegisterModelFactory

from hope_dedup_engine.apps.security.models import System


class SystemFactory(AutoRegisterModelFactory):
    name = factory.Sequence(lambda n: "System-%03d" % n)

    class Meta:
        model = System
        django_get_or_create = ("name",)
