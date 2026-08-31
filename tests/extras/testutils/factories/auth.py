import factory
from factory import fuzzy
from hope_api_auth.models import APILogEntry, APIToken

from hope_dedup_engine.apps.api.grant import Grant

from .base import AutoRegisterModelFactory
from .user import UserFactory


class APITokenFactory(AutoRegisterModelFactory):
    user = factory.SubFactory(UserFactory)
    grants = [Grant.API_DEDUP.value]

    class Meta:
        model = APIToken


class APILogEntryFactory(AutoRegisterModelFactory):
    token = factory.SubFactory(APITokenFactory)
    status_code = fuzzy.FuzzyInteger(200, 599)

    class Meta:
        model = APILogEntry
