from collections.abc import Generator
from itertools import combinations

from factory import SubFactory, fuzzy
from factory.django import DjangoModelFactory
from testutils.factories import ExternalSystemFactory, UserFactory

from hope_dedup_engine.apps.api.deduplication.registry import DuplicateKeyPair
from hope_dedup_engine.apps.api.models import DeduplicationSet, HDEToken
from hope_dedup_engine.apps.api.models.deduplication import (
    Duplicate,
    IgnoredKeyPair,
    Image,
)


class TokenFactory(DjangoModelFactory):
    user = SubFactory(UserFactory)

    class Meta:
        model = HDEToken


class DeduplicationSetFactory(DjangoModelFactory):
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
    first_reference_pk = fuzzy.FuzzyText()
    second_reference_pk = fuzzy.FuzzyText()
    score = fuzzy.FuzzyFloat(low=0, high=1)

    class Meta:
        model = Duplicate


class IgnoredKeyPairFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)
    first_reference_pk = fuzzy.FuzzyText()
    second_reference_pk = fuzzy.FuzzyText()

    class Meta:
        model = IgnoredKeyPair


class AllDuplicateFinder:
    weight = 1

    def __init__(self, deduplication_set: DeduplicationSet) -> None:
        self.deduplication_set = deduplication_set

    def run(self) -> Generator[DuplicateKeyPair, None, None]:
        reference_pks = self.deduplication_set.image_set.values_list(
            "reference_pk", flat=True
        ).order_by("reference_pk")
        for first, second in combinations(reference_pks, 2):
            yield first, second, 1.0


class NoDuplicateFinder:
    weight = 1

    def run(self) -> Generator[DuplicateKeyPair, None, None]:
        # empty generator
        return
        yield
