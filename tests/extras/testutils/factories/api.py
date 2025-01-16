from uuid import uuid4

from factory import Factory, SubFactory, fuzzy, lazy_attribute
from factory.django import DjangoModelFactory
from testutils.factories import ExternalSystemFactory, UserFactory

from hope_dedup_engine.apps.api.deduplication.config import (
    DeduplicateOptions,
    DeduplicationSetConfig,
    EncodingOptions,
    ModelOptions,
)
from hope_dedup_engine.apps.api.models import DedupJob, DeduplicationSet, HDEToken
from hope_dedup_engine.apps.api.models.config import Config
from hope_dedup_engine.apps.api.models.deduplication import (
    Finding,
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
    settings = {}

    class Meta:
        model = Config


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


class FindingFactory(DjangoModelFactory):
    class Meta:
        model = Finding
        django_get_or_create = (
            "deduplication_set",
            "first_reference_pk",
            "second_reference_pk",
        )

    deduplication_set = SubFactory(DeduplicationSetFactory)
    first_reference_pk = fuzzy.FuzzyText()
    first_filename = fuzzy.FuzzyText()
    second_reference_pk = fuzzy.FuzzyText()
    second_filename = fuzzy.FuzzyText()
    score = fuzzy.FuzzyFloat(low=0, high=1)

    @lazy_attribute
    def status_code(self):
        return (
            fuzzy.FuzzyChoice(list(Image.StatusCode.values)).fuzz().value
            if self.score == 0
            else None
        )


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


class DedupJobFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)

    class Meta:
        model = DedupJob


class ModelOptionsFactory(Factory):
    class Meta:
        model = ModelOptions

    model_name = fuzzy.FuzzyChoice(["model1", "model2"])
    detector_backend = fuzzy.FuzzyChoice(["backend1", "backend2"])


class EncodingOptionsFactory(ModelOptionsFactory):
    class Meta:
        model = EncodingOptions


class DeduplicateOptionsFactory(ModelOptionsFactory):
    class Meta:
        model = DeduplicateOptions

    threshold = fuzzy.FuzzyFloat(0.1, 1.0)
    silent = fuzzy.FuzzyChoice([True, False])


class DeduplicationSetConfigFactory(Factory):
    class Meta:
        model = DeduplicationSetConfig

    deduplication_set_id = uuid4()
    encoding = SubFactory(EncodingOptionsFactory)
    deduplicate = SubFactory(DeduplicateOptionsFactory)
