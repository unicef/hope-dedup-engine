from factory import SubFactory, fuzzy
from factory.django import DjangoModelFactory
from rest_framework.authtoken.models import Token

from hope_dedup_engine.apps.public_api.models import DeduplicationSet
from testutils.factories import UserFactory


class TokenFactory(DjangoModelFactory):
    user = SubFactory(UserFactory)

    class Meta:
        model = Token


class DeduplicationSetFactory(DjangoModelFactory):
    name = fuzzy.FuzzyText()
    reference_pk = fuzzy.FuzzyInteger(low=1)

    class Meta:
        model = DeduplicationSet
