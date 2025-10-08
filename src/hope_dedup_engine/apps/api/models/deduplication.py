from __future__ import annotations

import traceback
from typing import Any, Final, override, TYPE_CHECKING
from uuid import uuid4

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Exists, OuterRef, Q

from hope_dedup_engine.apps.api.utils.pairs.query import count_pairs, pairs
from hope_dedup_engine.apps.security.models import System

if TYPE_CHECKING:
    from hope_dedup_engine.type_aliases import EncodingType, FindingType, IgnoredPairType
    from collections.abc import Generator

REFERENCE_PK_LENGTH: Final[int] = 100
FILENAME_LENGTH: Final[int] = 255
MAX_ERROR_LENGTH: Final[int] = 255


class DeduplicationSet(models.Model):
    """Bucket for entries we want to deduplicate."""

    class State(models.IntegerChoices):
        READY = 0, "Ready"  # Deduplication set is created or already processed
        MODIFIED = (
            1,
            "Modified",
        )  # Images are added to deduplication set, but not yet processed
        PROCESSING = 2, "Processing"  # deduplication set is being processed
        FAILED = 3, "Failed"  # an error occurred

    id = models.UUIDField(primary_key=True, default=uuid4)
    name = models.CharField(max_length=128, unique=True, null=True, blank=True, db_index=True)
    description = models.TextField(null=True, blank=True)
    reference_pk = models.CharField(max_length=REFERENCE_PK_LENGTH)  # source_id
    state = models.IntegerField(choices=State, default=State.READY, db_column="state")
    deleted = models.BooleanField(null=False, blank=False, default=False)
    system = models.ForeignKey(System, on_delete=models.CASCADE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)
    notification_url = models.CharField(max_length=255, null=True, blank=True)
    config = models.ForeignKey("Config", null=True, on_delete=models.SET_NULL)
    error = models.CharField(max_length=MAX_ERROR_LENGTH, null=True, blank=True)

    def __str__(self) -> str:
        return self.name or f"ID: {self.pk}"

    @property
    def encodings_query(self) -> models.QuerySet[Encoding]:
        return Encoding.objects.filter(filename__in=self.image_set.values_list("filename", flat=True)).order_by("id")

    def filenames_without_encodings(self) -> list[str]:
        enc_facial_errors = Encoding.objects.filter(filename=OuterRef("filename")).filter(
            Q(embedding__isnull=False) | Q(status_code__in=ImageErrorGroup.FACE_DETECT)
        )
        return list(self.image_set.filter(~Exists(enc_facial_errors)).values_list("filename", flat=True))

    def get_findings(self) -> FindingType:
        return list(self.finding_set.values_list("first_reference_pk", "second_reference_pk", "score"))

    def get_ignored_pairs(self) -> IgnoredPairType:
        return list(self.ignoredreferencepkpair_set.values_list("first", "second")) + list(
            self.ignoredfilenamepair_set.values_list("first", "second")
        )

    def update_encodings(self, encodings: EncodingType) -> None:
        Encoding.objects.bulk_create(
            [
                Encoding(
                    filename=fn,
                    embedding=v if isinstance(v, list) else None,
                    status_code=v if isinstance(v, int) else None,
                )
                for fn, v in sorted(encodings.items())  # sort encodings to prevent deadlock
                if v is not None
            ],
            update_conflicts=True,
            update_fields=["embedding", "status_code"],
            unique_fields=["filename"],
        )

    def update_findings(self, findings: FindingType) -> None:
        images = Image.objects.filter(deduplication_set=self).values("filename", "reference_pk")
        filename_to_reference_pk = {img["filename"]: img["reference_pk"] for img in images} | {"": ""}
        findings_to_create = [
            Finding(
                deduplication_set=self,
                first_filename=f[0],
                first_reference_pk=filename_to_reference_pk.get(f[0]),
                second_filename=f[1],
                second_reference_pk=filename_to_reference_pk.get(f[1]),
                score=f[2],
                status_code=f[3],
            )
            for f in findings
        ]
        Finding.objects.bulk_create(findings_to_create, ignore_conflicts=True)

    def set_state(self, state: State, error: Exception | None = None) -> None:
        self.state = state.value
        if error:
            formatted_error = "".join(traceback.format_exception(error))
            self.error = formatted_error[:MAX_ERROR_LENGTH]
        else:
            self.error = None
        self.save(update_fields=["state", "error"])


class ImageManager(models.Manager["Image"]):
    def create(self, **kwargs: Any) -> "Image":
        """We override this method to make image creation idempotent."""
        deduplication_set = kwargs.pop("deduplication_set")
        reference_pk = kwargs.pop("reference_pk")
        image, _ = self.update_or_create(
            deduplication_set=deduplication_set, reference_pk=reference_pk, defaults=kwargs
        )
        return image


class Image(models.Model):
    """# TODO: Rename to Entity/Entry. Enforce per-set uniqueness of identifiers (filename/reference_pk)."""

    class StatusCode(models.IntegerChoices):
        DEDUPLICATE_SUCCESS = 200, "deduplication success"
        NO_FILE_FOUND = 404, "no file found"
        NO_FACE_DETECTED = 412, "no face detected"
        MULTIPLE_FACES_DETECTED = 429, "multiple faces detected"
        GENERIC_ERROR = 500, "generic error"

    id = models.UUIDField(primary_key=True, default=uuid4)
    deduplication_set = models.ForeignKey(DeduplicationSet, on_delete=models.CASCADE)
    reference_pk = models.CharField(max_length=REFERENCE_PK_LENGTH)
    filename = models.CharField(max_length=FILENAME_LENGTH)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    objects = ImageManager()

    class Meta:
        indexes = [
            models.Index(fields=["deduplication_set", "filename"]),
        ]
        unique_together = [
            # Here we assume reference_pk is unique per deduplication set
            ("deduplication_set", "reference_pk"),
        ]

    def __str__(self) -> str:
        return f"Image {self.filename}"


class ImageErrorGroup:
    FACE_DETECT = (Image.StatusCode.NO_FACE_DETECTED, Image.StatusCode.MULTIPLE_FACES_DETECTED)
    SYSTEM = (Image.StatusCode.NO_FILE_FOUND, Image.StatusCode.GENERIC_ERROR)


class Finding(models.Model):
    """Couple of finding entities."""

    deduplication_set = models.ForeignKey(DeduplicationSet, on_delete=models.CASCADE)
    first_reference_pk = models.CharField(max_length=REFERENCE_PK_LENGTH, verbose_name="First reference")
    first_filename = models.CharField(default="", max_length=FILENAME_LENGTH)
    second_reference_pk = models.CharField(default="", max_length=REFERENCE_PK_LENGTH, verbose_name="Second reference")
    second_filename = models.CharField(default="", max_length=FILENAME_LENGTH)
    score = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        verbose_name="Similarity Score",
    )
    status_code = models.IntegerField(choices=Image.StatusCode, default=Image.StatusCode.DEDUPLICATE_SUCCESS)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["deduplication_set", "-updated_at", "-id"], name="finding_order_idx"),
            models.Index(fields=["deduplication_set", "first_reference_pk"], name="finding_first_ref_idx"),
            models.Index(fields=["deduplication_set", "second_reference_pk"], name="finding_second_ref_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["deduplication_set", "first_reference_pk", "second_reference_pk"],
                name="unique_finding",
            ),
        ]

    def __str__(self) -> str:
        return f"Finding({self.first_filename}, {self.second_filename})"


class IgnoredPair(models.Model):
    deduplication_set = models.ForeignKey(DeduplicationSet, on_delete=models.CASCADE)

    class Meta:
        abstract = True

    @override
    def save(self, **kwargs: Any) -> None:
        self.first, self.second = sorted((self.first, self.second))
        super().save(**kwargs)


UNIQUE_FOR_IGNORED_PAIR = (
    "deduplication_set",
    "first",
    "second",
)


class IgnoredReferencePkPair(IgnoredPair):
    first = models.CharField(max_length=REFERENCE_PK_LENGTH)
    second = models.CharField(max_length=REFERENCE_PK_LENGTH)

    class Meta:
        constraints = [models.UniqueConstraint(fields=UNIQUE_FOR_IGNORED_PAIR, name="unique_ignored_ref_pair")]

    def __str__(self) -> str:
        return f"IgnoredReferencePkPair({self.first}, {self.second})"


class IgnoredFilenamePair(IgnoredPair):
    first = models.CharField(max_length=FILENAME_LENGTH)
    second = models.CharField(max_length=FILENAME_LENGTH)

    class Meta:
        constraints = [models.UniqueConstraint(fields=UNIQUE_FOR_IGNORED_PAIR, name="unique_ignored_filename_pair")]

    def __str__(self) -> str:
        return f"IgnoredFilenamePair({self.first}, {self.second})"


class Encoding(models.Model):
    filename = models.CharField(max_length=FILENAME_LENGTH, unique=True)
    embedding = ArrayField(models.FloatField(), null=True, blank=True)
    status_code = models.IntegerField(choices=Image.StatusCode, null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(embedding__isnull=False, status_code__isnull=True)
                    | Q(embedding__isnull=True, status_code__isnull=False)
                ),
                name="encoding_embedding_or_status",
            ),
        ]

    def __str__(self) -> str:
        return f"Encoding({self.filename})"


class DeduplicationChunk(models.Model):
    deduplication_set = models.ForeignKey(DeduplicationSet, on_delete=models.CASCADE)
    start = models.IntegerField()
    end = models.IntegerField()
    ready = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"DeduplicationChunk({self.deduplication_set.name}, {self.start}, {self.end}, {self.ready})"

    @staticmethod
    def create_chunks(deduplication_set: DeduplicationSet, size: int) -> Generator[int]:
        total_pairs = count_pairs(deduplication_set.encodings_query)
        max_pair = deduplication_set.deduplicationchunk_set.aggregate(models.Max("end", default=0))["end__max"]
        for start in range(max_pair, total_pairs, size):
            end = min(start + size, total_pairs)
            deduplication_chunk = DeduplicationChunk.objects.create(
                deduplication_set=deduplication_set, start=start, end=end
            )
            yield deduplication_chunk.pk

    def pairs(self) -> Generator[tuple[Encoding, Encoding]]:
        yield from pairs(self.deduplication_set.encodings_query, self.start, self.end)
