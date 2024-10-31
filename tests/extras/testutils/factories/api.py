from factory import SubFactory, fuzzy, post_generation
from factory.django import DjangoModelFactory
from testutils.factories import ExternalSystemFactory, UserFactory

from hope_dedup_engine.apps.api.models import DeduplicationSet, HDEToken
from hope_dedup_engine.apps.api.models.config import Config
from hope_dedup_engine.apps.api.models.deduplication import (
    Duplicate,
    IgnoredFilenamePair,
    IgnoredReferencePkPair,
    Image,
)


class TokenFactory(DjangoModelFactory):
    user = SubFactory(UserFactory)

    class Meta:
        model = HDEToken


class ConfigFactory(DjangoModelFactory):
    name = fuzzy.FuzzyText()

    class Meta:
        model = Config

    @post_generation
    def settings(self, create, extracted, **kwargs):
        self.settings = {
            "detection": {"confidence": fuzzy.FuzzyFloat(0.1, 1.0).fuzz()},
            "duplicates": {"tolerance": fuzzy.FuzzyFloat(0.1, 1.0).fuzz()},
            "recognition": {
                "model": fuzzy.FuzzyChoice(["small", "large"]).fuzz(),
                "num_jitters": fuzzy.FuzzyInteger(1, 10).fuzz(),
            },
        }
        if create:
            self.save()


class DeduplicationSetFactory(DjangoModelFactory):
    reference_pk = fuzzy.FuzzyText()
    external_system = SubFactory(ExternalSystemFactory)
    state = DeduplicationSet.State.CLEAN
    notification_url = fuzzy.FuzzyText(prefix="https://")
    config = SubFactory(ConfigFactory)

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
    first_reference_pk = fuzzy.FuzzyText()
    second_reference_pk = fuzzy.FuzzyText()
    score = fuzzy.FuzzyFloat(low=0, high=1)

    class Meta:
        model = Duplicate


class IgnoredFilenamePairFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)
    first = fuzzy.FuzzyText()
    second = fuzzy.FuzzyText()

    class Meta:
        model = IgnoredFilenamePair


class IgnoredReferencePkPairFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)
    first = fuzzy.FuzzyText()
    second = fuzzy.FuzzyText()

    class Meta:
        model = IgnoredReferencePkPair
