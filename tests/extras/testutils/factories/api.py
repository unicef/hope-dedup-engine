from factory import SubFactory, fuzzy
from factory.django import DjangoModelFactory
from testutils.factories import ExternalSystemFactory

from hope_dedup_engine.apps.api.models import DeduplicationSet, HDEToken
from hope_dedup_engine.apps.api.models.deduplication import Image


class TokenFactory(DjangoModelFactory):
    class Meta:
        model = HDEToken


class DeduplicationSetFactory(DjangoModelFactory):
    name = fuzzy.FuzzyText()
    reference_pk = fuzzy.FuzzyInteger(low=1)
    external_system = SubFactory(ExternalSystemFactory)
    state = DeduplicationSet.State.CLEAN

    class Meta:
        model = DeduplicationSet


class ImageFactory(DjangoModelFactory):
    filename = fuzzy.FuzzyText()
    deduplication_set = SubFactory(DeduplicationSetFactory)

    class Meta:
        model = Image
