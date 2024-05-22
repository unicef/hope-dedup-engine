from factory import SubFactory, fuzzy
from factory.django import DjangoModelFactory
from testutils.factories import ExternalSystemFactory

from hope_dedup_engine.apps.api.models import DeduplicationSet, HDEToken
from hope_dedup_engine.apps.api.models.deduplication import Duplicate, Image


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
    deduplication_set = SubFactory(DeduplicationSetFactory)
    filename = fuzzy.FuzzyText()
    reference_pk = fuzzy.FuzzyInteger(low=1)

    class Meta:
        model = Image


class DuplicateFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)
    first_filename = fuzzy.FuzzyText()
    first_reference_pk = fuzzy.FuzzyInteger(low=1)
    second_filename = fuzzy.FuzzyText()
    second_reference_pk = fuzzy.FuzzyInteger(low=1)
    score = fuzzy.FuzzyFloat(low=0, high=1)

    class Meta:
        model = Duplicate
