from uuid import uuid4, UUID

from factory import Factory, SubFactory, fuzzy, lazy_attribute, Trait, SelfAttribute
from factory.django import DjangoModelFactory

from hope_dedup_engine.apps.api.deduplication.config import (
    DeduplicateOptions,
    DeduplicationSetConfig,
    EncodingOptions,
    ModelOptions,
)
from hope_dedup_engine.apps.api.models import MainJob, DeduplicationSet, HDEToken
from hope_dedup_engine.apps.api.models.deduplication import (
    Finding,
    IgnoredFilenamePair,
    IgnoredReferencePkPair,
    Encoding,
    DeduplicationSetGroup,
)
from hope_dedup_engine.apps.api.models.jobs import (
    EncodeChunkJob,
    DedupeChunkJob,
    CallbackFindingsJob,
    DeduplicateDatasetJob,
    SyncDnnFilesJob,
    DedupJob,
)
from testutils.factories import SystemFactory, UserFactory


class HDETokenFactory(DjangoModelFactory):
    user = SubFactory(UserFactory)
    system = SubFactory(SystemFactory)

    class Meta:
        model = HDEToken


class DeduplicationSetGroupFactory(DjangoModelFactory):
    reference_pk = fuzzy.FuzzyText()
    name = None
    system = SubFactory(SystemFactory)

    class Meta:
        model = DeduplicationSetGroup


class DeduplicationSetFactory(DjangoModelFactory):
    group = SubFactory(DeduplicationSetGroupFactory)
    state = DeduplicationSet.State.READY
    notification_url = fuzzy.FuzzyText(prefix="https://")
    settings = {
        "threshold": 0.9,
    }

    class Meta:
        model = DeduplicationSet


class EncodingFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)
    filename = fuzzy.FuzzyText()
    reference_pk = fuzzy.FuzzyText()
    embedding = fuzzy.FuzzyAttribute(lambda: [fuzzy.FuzzyFloat(0.0, 1.0).fuzz() for _ in range(8)])
    embedding_status_code = None

    class Meta:
        model = Encoding

    class Params:
        face_detect_error = Trait(
            embedding=None,
            embedding_status_code=fuzzy.FuzzyChoice(
                [
                    Encoding.StatusCode.NO_FACE_DETECTED.value,
                    Encoding.StatusCode.MULTIPLE_FACES_DETECTED.value,
                    Encoding.StatusCode.FACE_NOT_ACCEPTED.value,
                ]
            ),
        )
        system_error = Trait(
            embedding=None,
            embedding_status_code=fuzzy.FuzzyChoice(
                [
                    Encoding.StatusCode.FILE_NOT_FOUND.value,
                    Encoding.StatusCode.GENERIC_ERROR.value,
                ]
            ),
        )


class FindingFactory(DjangoModelFactory):
    class Meta:
        model = Finding
        django_get_or_create = (
            "deduplication_set",
            "first_encoding",
            "second_encoding",
        )

    deduplication_set = SubFactory(DeduplicationSetFactory)
    first_encoding = SubFactory(EncodingFactory, deduplication_set=SelfAttribute("..deduplication_set"))
    second_encoding = SubFactory(EncodingFactory, deduplication_set=SelfAttribute("..deduplication_set"))
    score = fuzzy.FuzzyFloat(low=0, high=1)

    @lazy_attribute
    def status_code(self):
        return (
            fuzzy.FuzzyChoice(
                [
                    Encoding.StatusCode.FILE_NOT_FOUND.value,
                    Encoding.StatusCode.NO_FACE_DETECTED.value,
                    Encoding.StatusCode.MULTIPLE_FACES_DETECTED.value,
                    Encoding.StatusCode.GENERIC_ERROR.value,
                ]
            )
            .fuzz()
            .value
            if self.score == 0
            else Encoding.StatusCode.DEDUPLICATE_SUCCESS.value
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


class MainJobFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)

    class Meta:
        model = MainJob


class EncodeChunkJobFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)
    encoding_ids: list[UUID] = []

    class Meta:
        model = EncodeChunkJob


class DedupeChunkJobFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)
    encoding_ids0: list[UUID] = []
    encoding_ids1: list[UUID] = []

    class Meta:
        model = DedupeChunkJob


class CallbackFindingsJobFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)

    class Meta:
        model = CallbackFindingsJob


class DeduplicateDatasetJobFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)

    class Meta:
        model = DeduplicateDatasetJob


class SyncDnnFilesJobFactory(DjangoModelFactory):
    class Meta:
        model = SyncDnnFilesJob


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
