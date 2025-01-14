from factory import Factory, Faker, LazyFunction, SubFactory, fuzzy, post_generation
from factory.django import DjangoModelFactory
from testutils.factories import ExternalSystemFactory, UserFactory

from hope_dedup_engine.apps.api.deduplication.config import (
    ConfigDefaults,
    DetectionConfig,
    DuplicatesConfig,
    RecognitionConfig,
)
from hope_dedup_engine.apps.api.models import DedupJob, DeduplicationSet, HDEToken
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


class DedupJobFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)

    class Meta:
        model = DedupJob


class DetectionConfigFactory(Factory):
    class Meta:
        model = DetectionConfig

    dnn_files_source = Faker("word")
    dnn_backend = fuzzy.FuzzyInteger(0, 5)
    dnn_target = fuzzy.FuzzyInteger(0, 5)
    blob_from_image_scale_factor = fuzzy.FuzzyFloat(0.5, 1.5)
    blob_from_image_mean_values = LazyFunction(lambda: (104.0, 177.0, 123.0))
    confidence = fuzzy.FuzzyFloat(0.1, 1.0)
    nms_threshold = fuzzy.FuzzyFloat(0.1, 1.0)


class RecognitionConfigFactory(Factory):
    class Meta:
        model = RecognitionConfig

    num_jitters = fuzzy.FuzzyInteger(0, 5)
    model = fuzzy.FuzzyChoice(["small", "large"])
    preprocessors = []


class DuplicatesConfigFactory(Factory):
    class Meta:
        model = DuplicatesConfig

    tolerance = fuzzy.FuzzyFloat(0.1, 1.0)


class ConfigDefaultsFactory(Factory):
    class Meta:
        model = ConfigDefaults

    detection = SubFactory(DetectionConfigFactory)
    recognition = SubFactory(RecognitionConfigFactory)
    duplicates = SubFactory(DuplicatesConfigFactory)

    # @post_generation
    # def apply_overrides(self, create, extracted, **kwargs):
    #         self.apply_config_overrides(extracted)
