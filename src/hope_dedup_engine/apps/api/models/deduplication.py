import traceback
from typing import Any, Final, override
from uuid import uuid4

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, QuerySet

from hope_dedup_engine.apps.security.models import System

REFERENCE_PK_LENGTH: Final[int] = 100
FILENAME_LENGTH: Final[int] = 255
MAX_ERROR_LENGTH: Final[int] = 255


class DeduplicationSetGroup(models.Model):
    reference_pk = models.CharField(max_length=REFERENCE_PK_LENGTH, unique=True)  # source_id
    system = models.ForeignKey(System, on_delete=models.CASCADE)
    settings = models.JSONField(default=dict, null=True, blank=True)
    deleted = models.BooleanField(null=False, blank=False, default=False)

    def __str__(self) -> str:
        return f"{self.reference_pk}({self.system.name})"


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
        INACTIVE = 4, "Inactive"

    id = models.UUIDField(primary_key=True, default=uuid4)
    group = models.ForeignKey(DeduplicationSetGroup, on_delete=models.CASCADE)
    name = models.CharField(max_length=128, unique=True, null=True, blank=True, db_index=True)
    description = models.TextField(null=True, blank=True)
    state = models.IntegerField(choices=State, default=State.READY, db_column="state")
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
    notify = models.BooleanField(default=True)
    error = models.CharField(max_length=MAX_ERROR_LENGTH, null=True, blank=True)
    settings = models.JSONField(default=dict, null=True, blank=True)

    def __str__(self) -> str:
        return self.name or f"ID: {self.pk}"

    def encodings_with_embeddings(self) -> QuerySet["Encoding"]:
        return self.encoding_set.filter(embedding__isnull=False)

    def encodings_without_embeddings(self) -> QuerySet["Encoding"]:
        return self.encoding_set.filter(embedding__isnull=True).exclude(
            embedding_status_code__in=EncodingErrorGroup.FACE_DETECT
        )

    def get_ignored_pairs(self) -> set[frozenset[str]]:
        return set(
            map(
                frozenset,
                tuple(self.ignoredreferencepkpair_set.values_list("first", "second"))
                + tuple(self.ignoredfilenamepair_set.values_list("first", "second")),
            )
        )

    def set_state(self, state: State, error: Exception | None = None) -> None:
        self.state = state.value
        if error:
            formatted_error = "".join(traceback.format_exception(error))
            self.error = formatted_error[:MAX_ERROR_LENGTH]
        else:
            self.error = None
        self.save(update_fields=["state", "error"])


class EncodingManager(models.Manager["Encoding"]):
    def create(self, **kwargs: Any) -> "Encoding":
        """We override this method to make image creation idempotent."""
        deduplication_set = kwargs.pop("deduplication_set")
        reference_pk = kwargs.pop("reference_pk")
        image, _ = self.update_or_create(
            deduplication_set=deduplication_set, reference_pk=reference_pk, defaults=kwargs
        )
        return image


class Encoding(models.Model):
    """# TODO: Enforce per-set uniqueness of identifiers (filename/reference_pk)."""

    class State(models.IntegerChoices):
        ACTIVE = 0, "Active"
        APPROVED = 1, "Approved"
        REJECTED = 2, "Rejected"

    class StatusCode(models.IntegerChoices):
        DEDUPLICATE_SUCCESS = 200, "deduplication success"
        FILE_NOT_FOUND = 404, "no file found"
        NO_FACE_DETECTED = 412, "no face detected"
        FACE_NOT_ACCEPTED = 416, "face was detected but did not meet confidence threshold"
        MULTIPLE_FACES_DETECTED = 429, "multiple faces detected"
        GENERIC_ERROR = 500, "generic error"

    id = models.UUIDField(primary_key=True, default=uuid4)
    state = models.IntegerField(choices=State, default=State.ACTIVE)
    deduplication_set = models.ForeignKey(DeduplicationSet, on_delete=models.CASCADE)
    reference_pk = models.CharField(max_length=REFERENCE_PK_LENGTH)
    filename = models.CharField(max_length=FILENAME_LENGTH)
    embedding = ArrayField(models.FloatField(), null=True, blank=True)
    embedding_status_code = models.IntegerField(choices=StatusCode, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    objects = EncodingManager()

    class Meta:
        indexes = [
            models.Index(fields=["deduplication_set", "filename"]),
        ]
        unique_together = [
            # Here we assume reference_pk is unique per deduplication set
            ("deduplication_set", "reference_pk"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(embedding__isnull=True, embedding_status_code__isnull=True)
                    | Q(embedding__isnull=False, embedding_status_code__isnull=True)
                    | Q(embedding__isnull=True, embedding_status_code__isnull=False)
                ),
                name="encoding_embedding_or_status",
            ),
        ]

    def __str__(self) -> str:
        return f"Image {self.filename}"


class EncodingErrorGroup:
    FACE_DETECT = (
        Encoding.StatusCode.FACE_NOT_ACCEPTED,
        Encoding.StatusCode.NO_FACE_DETECTED,
        Encoding.StatusCode.MULTIPLE_FACES_DETECTED,
    )
    SYSTEM = (Encoding.StatusCode.FILE_NOT_FOUND, Encoding.StatusCode.GENERIC_ERROR)


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
    status_code = models.IntegerField(choices=Encoding.StatusCode, default=Encoding.StatusCode.DEDUPLICATE_SUCCESS)
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
