from uuid import uuid4

from factory import Factory, SubFactory, fuzzy, lazy_attribute, Trait, SelfAttribute
from factory.django import DjangoModelFactory

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from hope_dedup_engine.apps.api.models import MainJob, DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import (
    Finding,
    Encoding,
    DeduplicationSetGroup,
)
from hope_dedup_engine.apps.api.models.jobs import (
    SyncDnnFilesJob,
    DedupJob,
)


class DeduplicationSetGroupFactory(DjangoModelFactory):
    reference_pk = fuzzy.FuzzyText()
    name = None

    class Meta:
        model = DeduplicationSetGroup


class DeduplicationSetFactory(DjangoModelFactory):
    group = SubFactory(DeduplicationSetGroupFactory)
    state = DeduplicationSet.State.READY
    notification_url = fuzzy.FuzzyText(prefix="https://")
    findings_count = 0

    class Meta:
        model = DeduplicationSet
        exclude = ("findings_count",)


class EncodingFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)
    # `filename` is a FileField; assigning a plain string sets the underlying DB value
    # without touching storage (sufficient for tests that mock _load_image).
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


class DedupJobFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)

    class Meta:
        model = DedupJob


class MainJobFactory(DjangoModelFactory):
    deduplication_set = SubFactory(DeduplicationSetFactory)

    class Meta:
        model = MainJob


class SyncDnnFilesJobFactory(DjangoModelFactory):
    class Meta:
        model = SyncDnnFilesJob


class DeduplicationSetConfigFactory(Factory):
    class Meta:
        model = DeduplicationSetConfig

    deduplication_set_id = uuid4()
    recognition_model = fuzzy.FuzzyChoice(["Facenet512", "VGG-Face"])
    detector_backend = fuzzy.FuzzyChoice(["retinaface", "mtcnn"])
    distance_metric = fuzzy.FuzzyChoice(["cosine", "euclidean"])
    face_detection_confidence_threshold = fuzzy.FuzzyFloat(0.5, 0.99)
    duplicate_confidence_threshold = fuzzy.FuzzyFloat(30.0, 80.0)
