from factory import SubFactory, fuzzy
from factory.django import DjangoModelFactory
from testutils.factories import ExternalSystemFactory, UserFactory

from hope_dedup_engine.apps.api.models import DeduplicationSet, HDEToken
from hope_dedup_engine.apps.api.models.deduplication import Duplicate, Image


class TokenFactory(DjangoModelFactory):
    user = SubFactory(UserFactory)

    class Meta:
        model = HDEToken


class DeduplicationSetFactory(DjangoModelFactory):
    name = fuzzy.FuzzyText()
    reference_pk = fuzzy.FuzzyText()
    external_system = SubFactory(ExternalSystemFactory)
    state = DeduplicationSet.State.CLEAN
    notification_url = fuzzy.FuzzyText()

    class Meta:
        model = DeduplicationSet


class ImageFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)
    filename = fuzzy.FuzzyText()
    reference_pk = fuzzy.FuzzyText()

    class Meta:
        model = Image


class DuplicateFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)
    first_filename = fuzzy.FuzzyText()
    first_reference_pk = fuzzy.FuzzyText()
    second_filename = fuzzy.FuzzyText()
    second_reference_pk = fuzzy.FuzzyText()
    score = fuzzy.FuzzyFloat(low=0, high=1)

    class Meta:
        model = Duplicate
