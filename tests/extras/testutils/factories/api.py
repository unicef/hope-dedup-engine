from factory import fuzzy
from factory.django import DjangoModelFactory

from hope_dedup_engine.apps.public_api.models import DeduplicationSet, HDEToken
from hope_dedup_engine.apps.public_api.models.deduplication import Image


class TokenFactory(DjangoModelFactory):
    class Meta:
        model = HDEToken


class DeduplicationSetFactory(DjangoModelFactory):
    name = fuzzy.FuzzyText()
    reference_pk = fuzzy.FuzzyInteger(low=1)

    class Meta:
        model = DeduplicationSet


class ImageFactory(DjangoModelFactory):
    filename = fuzzy.FuzzyText()

    class Meta:
        model = Image
