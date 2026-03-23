import traceback
from typing import Any, Final, override
from uuid import uuid4

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, QuerySet

from hope_dedup_engine.apps.api.utils.data_url import inline_label
from hope_dedup_engine.apps.security.models import System

REFERENCE_PK_LENGTH: Final[int] = 100
FILENAME_LENGTH: Final[int] = 255
MAX_ERROR_LENGTH: Final[int] = 255


class DeduplicationSetGroup(models.Model):
    reference_pk = models.CharField(
        max_length=REFERENCE_PK_LENGTH, unique=True, help_text="External id used to group deduplication sets."
    )
    name = models.CharField(
        max_length=128, null=True, blank=True, db_index=True, help_text="Deduplication set group name."
    )
    system = models.ForeignKey(System, on_delete=models.CASCADE, help_text="System API user belongs to.")
    settings = models.JSONField(
        default=dict, null=True, blank=True, help_text="Settings common for all deduplication sets in this group."
    )
    deleted = models.BooleanField(null=False, blank=False, default=False, help_text="Whether this group was deleted.")

    def __str__(self) -> str:
        return f"{self.name} ({self.reference_pk})"

    def has_calculated_embeddings(self) -> bool:
        return Encoding.objects.filter(
            deduplication_set__group=self,
            embedding__isnull=False,
        ).exists()

    def has_inactive_deduplication_sets(self) -> bool:
        return self.deduplicationset_set.filter(state=DeduplicationSet.State.INACTIVE).exists()


FAILED_STATE: Final[int] = 3
INACTIVE_STATE: Final[int] = 4
REJECTED_STATE: Final[int] = 5


class DeduplicationSet(models.Model):
    """Bucket for entries we want to deduplicate."""

    class State(models.IntegerChoices):
        READY = 0, "Ready"  # Deduplication set is created or already processed
        MODIFIED = (
            1,
            "Modified",
        )  # Images are added to deduplication set, but not yet processed
        PROCESSING = 2, "Processing"  # deduplication set is being processed
        FAILED = FAILED_STATE, "Failed"  # an error occurred
        INACTIVE = INACTIVE_STATE, "Inactive"  # set cannot be modified but takes part in the deduplication process
        REJECTED = REJECTED_STATE, "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid4, help_text="Deduplication set id.")
    group = models.ForeignKey(DeduplicationSetGroup, on_delete=models.CASCADE, help_text="Deduplication set group.")
    name = models.CharField(
        max_length=128, unique=True, null=True, blank=True, db_index=True, help_text="Deduplication set name."
    )
    description = models.TextField(null=True, blank=True, help_text="Deduplication set description.")
    state = models.IntegerField(
        choices=State, default=State.READY, db_column="state", help_text="Deduplication set state."
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
        help_text="User who created this deduplication set.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Date and time when this deduplication set was created."
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
        help_text="User who last updated this deduplication set.",
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Date and time when this deduplication set was last updated."
    )
    notification_url = models.CharField(max_length=255, null=True, blank=True, help_text="Notification url.")
    notify = models.BooleanField(
        default=True, help_text="Whether to send notifications about deduplication set state changes."
    )
    error = models.CharField(max_length=MAX_ERROR_LENGTH, null=True, blank=True, help_text="Error message.")

    class Meta:
        permissions = [
            ("clear_embeddings", "Can clear embeddings"),
            ("export_findings", "Can export findings"),
            ("process_encodings", "Can process encodings"),
            ("process_deduplicate", "Can process deduplication"),
            ("remove_findings", "Can remove findings"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["group"],
                condition=~Q(state=INACTIVE_STATE) & ~Q(state=REJECTED_STATE) & ~Q(state=FAILED_STATE),
                name="unique_active_deduplication_set_per_group",
            ),
        ]

    def __str__(self) -> str:
        return self.name or f"ID: {self.pk}"

    def encodings_with_embeddings(self) -> QuerySet["Encoding"]:
        return self.encoding_set.filter(embedding__isnull=False)

    def encodings_without_embeddings(self) -> QuerySet["Encoding"]:
        return self.encoding_set.filter(embedding__isnull=True).exclude(
            embedding_status_code__in=EncodingErrorGroup.FACE_DETECT + EncodingErrorGroup.IMAGE_QUALITY
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

    class StatusCode(models.IntegerChoices):
        DEDUPLICATE_SUCCESS = 200, "deduplication success"
        FILE_NOT_FOUND = 404, "no file found"
        NO_FACE_DETECTED = 412, "no face detected"
        FACE_NOT_ACCEPTED = 416, "face was detected but did not meet confidence threshold"
        INSUFFICIENT_FACE_COVERAGE = 417, "face does not cover sufficient part of the image"
        BAD_IMAGE_QUALITY = 418, "image quality below threshold"
        MULTIPLE_FACES_DETECTED = 429, "multiple faces detected"
        GENERIC_ERROR = 500, "generic error"

    id = models.UUIDField(primary_key=True, default=uuid4, help_text="Encoding id.")
    deduplication_set = models.ForeignKey(DeduplicationSet, on_delete=models.CASCADE, help_text="Deduplication set.")
    reference_pk = models.CharField(max_length=REFERENCE_PK_LENGTH, help_text="External id of the encoding.")
    filename = models.TextField(help_text="Filename or data URL used in encoding.")
    embedding = ArrayField(models.FloatField(), null=True, blank=True, help_text="Embedding vector.")
    embedding_status_code = models.IntegerField(
        choices=StatusCode, null=True, blank=True, help_text="Embedding status code."
    )
    face_coverage = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Face bbox area divided by image area (0..1).",
    )
    image_quality_scores = models.JSONField(
        null=True,
        blank=True,
        help_text="OFIQ quality scores dict, e.g. {'Sharpness': 23.4, 'DynamicRange': 88.0}.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
        help_text="User who created this encoding.",
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date and time when this encoding was created.")
    objects = EncodingManager()

    class Meta:
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
        permissions = [
            ("detect_faces", "Can detect faces"),
        ]

    def __str__(self) -> str:
        return f"Image {inline_label(self.filename)}"


class EncodingErrorGroup:
    FACE_DETECT = (
        Encoding.StatusCode.FACE_NOT_ACCEPTED,
        Encoding.StatusCode.NO_FACE_DETECTED,
        Encoding.StatusCode.INSUFFICIENT_FACE_COVERAGE,
        Encoding.StatusCode.MULTIPLE_FACES_DETECTED,
    )
    IMAGE_QUALITY = (Encoding.StatusCode.BAD_IMAGE_QUALITY,)
    SYSTEM = (Encoding.StatusCode.FILE_NOT_FOUND, Encoding.StatusCode.GENERIC_ERROR)


class Finding(models.Model):
    """Couple of finding entities."""

    deduplication_set = models.ForeignKey(DeduplicationSet, on_delete=models.CASCADE, help_text="Deduplication set.")
    first_encoding = models.ForeignKey(
        Encoding,
        on_delete=models.CASCADE,
        related_name="first_findings",
        help_text="First encoding in this potential duplicate pair.",
    )
    second_encoding = models.ForeignKey(
        Encoding,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="second_findings",
        help_text="Second encoding in this potential duplicate pair.",
    )
    score = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        verbose_name="Similarity Score",
        help_text="Similarity score between the two encodings.",
    )
    status_code = models.IntegerField(
        choices=Encoding.StatusCode, default=Encoding.StatusCode.DEDUPLICATE_SUCCESS, help_text="Finding status code."
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date and time when this finding was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="Date and time when this finding was updated.")

    class Meta:
        indexes = [
            models.Index(fields=["deduplication_set", "-updated_at", "-id"], name="finding_order_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["deduplication_set", "first_encoding", "second_encoding"],
                name="unique_finding",
            ),
        ]
        permissions = [
            ("view_finding_details", "Can view finding details"),
        ]

    def __str__(self) -> str:
        first = inline_label(self.first_encoding.filename)
        second = inline_label(self.second_encoding.filename) if self.second_encoding else "—"
        return f"Finding({first}, {second})"


class IgnoredPair(models.Model):
    deduplication_set = models.ForeignKey(DeduplicationSet, on_delete=models.CASCADE, help_text="Deduplication set.")

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
    first = models.CharField(max_length=REFERENCE_PK_LENGTH, help_text="First reference pk.")
    second = models.CharField(max_length=REFERENCE_PK_LENGTH, help_text="Second reference pk.")

    class Meta:
        constraints = [models.UniqueConstraint(fields=UNIQUE_FOR_IGNORED_PAIR, name="unique_ignored_ref_pair")]

    def __str__(self) -> str:
        return f"IgnoredReferencePkPair({self.first}, {self.second})"


class IgnoredFilenamePair(IgnoredPair):
    first = models.CharField(max_length=FILENAME_LENGTH, help_text="First filename.")
    second = models.CharField(max_length=FILENAME_LENGTH, help_text="Second filename.")

    class Meta:
        constraints = [models.UniqueConstraint(fields=UNIQUE_FOR_IGNORED_PAIR, name="unique_ignored_filename_pair")]

    def __str__(self) -> str:
        return f"IgnoredFilenamePair({self.first}, {self.second})"
