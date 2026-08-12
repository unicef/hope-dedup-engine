import factory
from django.utils import timezone
from factory import fuzzy
from hope_api_auth.models import APIToken, APILogEntry
from hope_dedup_engine.apps.api.grant import Grant

from testutils.factories import AutoRegisterModelFactory, UserFactory


class APITokenFactory(AutoRegisterModelFactory):
    user = factory.SubFactory(UserFactory)
    allowed_ips = ""
    grants = [Grant.API_READ_ONLY]
    valid_from = timezone.now
    valid_to = None
    created = factory.LazyFunction(timezone.now)

    class Meta:
        model = APIToken
        django_get_or_create = ("user",)


class APILogEntryFactory(AutoRegisterModelFactory):
    token = factory.SubFactory(APITokenFactory)
    status_code = fuzzy.FuzzyDecimal(200, 599)

    class Meta:
        model = APILogEntry
