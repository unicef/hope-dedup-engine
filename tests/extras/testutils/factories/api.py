from factory import fuzzy
from factory.django import DjangoModelFactory

from hope_dedup_engine.apps.public_api.models import DeduplicationSet, HDEToken


class TokenFactory(DjangoModelFactory):
    class Meta:
        model = HDEToken


class DeduplicationSetFactory(DjangoModelFactory):
    name = fuzzy.FuzzyText()
    reference_pk = fuzzy.FuzzyInteger(low=1)

    class Meta:
        model = DeduplicationSet
