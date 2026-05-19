import traceback
from typing import Any, Final
from uuid import uuid4

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.files.storage import storages
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q, QuerySet

from hope_dedup_engine.apps.security.models import System

REFERENCE_PK_LENGTH: Final[int] = 100
FILENAME_LENGTH: Final[int] = 255
MAX_ERROR_LENGTH: Final[int] = 255


def _images_storage():
    """Resolve the `images` storage lazily so test settings overrides take effect."""
    return storages["images"]


def encoding_image_upload_to(instance: "Encoding", filename: str) -> str:
    """Build the deterministic storage key for an Encoding image.

    `filename` is the basename (with extension) supplied by the caller via
    ContentFile(payload, name=...). We embed the group's reference_pk and the
    deduplication set id so that:

    - files belonging to the same external group are co-located on disk,
      making manual inspection / per-tenant cleanup easier; and
    - re-uploading the same (deduplication_set, reference_pk) overwrites the
      existing object instead of orphaning it.
    """
    group_ref = instance.deduplication_set.group.reference_pk
    return f"images/{group_ref}/{instance.deduplication_set_id}/{filename}"


class GroupSettingsError(Exception):
    pass


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
    processing_locked = models.BooleanField(
        default=False, help_text="Whether any deduplication task is currently running for this group."
    )

    def __str__(self) -> str:
        return f"{self.name} ({self.reference_pk})"

    def has_calculated_embeddings(self) -> bool:
        return Encoding.objects.filter(
            deduplication_set__group=self,
            embedding__isnull=False,
            deduplication_set__state__in=[
                DeduplicationSet.State.ENCODED,
                DeduplicationSet.State.DEDUPLICATED,
                DeduplicationSet.State.APPROVED,
                DeduplicationSet.State.ENCODING_FAILED,
                DeduplicationSet.State.DEDUPLICATION_FAILED,
            ],
        ).exists()

    def has_approved_deduplication_sets(self) -> bool:
        return self.deduplicationset_set.filter(state=DeduplicationSet.State.APPROVED).exists()

    def acquire_processing_lock(self) -> bool:
        with transaction.atomic():
            group = DeduplicationSetGroup.objects.select_for_update().get(pk=self.pk)
            if group.processing_locked:
                return False
            group.processing_locked = True
            group.save(update_fields=["processing_locked"])
            self.processing_locked = True
            return True

    def release_processing_lock(self) -> None:
        self.processing_locked = False
        self.save(update_fields=["processing_locked"])

    def update_settings(self, new_settings: dict) -> None:
        if not self.acquire_processing_lock():
            raise GroupSettingsError("Cannot change settings while a processing job is running.")

        try:
            if self.deduplicationset_set.filter(state=DeduplicationSet.State.APPROVED).exists():
                raise GroupSettingsError("Cannot change settings while an approved deduplication set exists.")

            with transaction.atomic():
                if not self.settings:
                    from hope_dedup_engine.apps.api.deduplication.config import get_default_group_settings  # noqa

                    self.settings = get_default_group_settings()

                for key, value in new_settings.items():
                    self.settings[key] = value
                self.save(update_fields=["settings"])

                self._clear_active_set_on_settings_change()
        finally:
            self.release_processing_lock()

    def _clear_active_set_on_settings_change(self) -> None:
        ds = (
            self.deduplicationset_set.filter(
                state__in=(DeduplicationSet.State.ENCODED, DeduplicationSet.State.DEDUPLICATED)
            )
            .order_by("-created_at")
            .first()
        )
        if not ds:
            return
        ds.clear_embeddings_data()
        ds.set_state(DeduplicationSet.State.READY)


ENCODING_FAILED_STATE: Final[int] = 5
DEDUPLICATION_FAILED_STATE: Final[int] = 8
APPROVED_STATE: Final[int] = 9
REJECTED_STATE: Final[int] = 10


class DeduplicationSet(models.Model):
    """Bucket for entries we want to deduplicate."""

    class State(models.IntegerChoices):
        EMPTY = 0, "Empty"
        UPLOADING_IN_PROGRESS = 1, "Uploading in progress"
        READY = 2, "Ready"
        ENCODING_IN_PROGRESS = 3, "Encoding in progress"
        ENCODED = 4, "Encoded"
        ENCODING_FAILED = ENCODING_FAILED_STATE, "Encoding failed"
        DEDUPLICATION_IN_PROGRESS = 6, "Deduplication in progress"
        DEDUPLICATED = 7, "Deduplicated"
        DEDUPLICATION_FAILED = DEDUPLICATION_FAILED_STATE, "Deduplication failed"
        APPROVED = APPROVED_STATE, "Approved"
        REJECTED = REJECTED_STATE, "Rejected"

    VALID_TRANSITIONS: Final[dict[int, tuple[int, ...]]] = {
        State.EMPTY: (State.UPLOADING_IN_PROGRESS,),
        State.UPLOADING_IN_PROGRESS: (State.UPLOADING_IN_PROGRESS, State.READY),
        State.READY: (State.ENCODING_IN_PROGRESS,),
        State.ENCODING_IN_PROGRESS: (State.ENCODED, State.ENCODING_FAILED),
        State.ENCODED: (State.DEDUPLICATION_IN_PROGRESS, State.ENCODING_IN_PROGRESS, State.READY),
        State.ENCODING_FAILED: (State.ENCODING_IN_PROGRESS,),
        State.DEDUPLICATION_IN_PROGRESS: (State.DEDUPLICATED, State.DEDUPLICATION_FAILED),
        State.DEDUPLICATED: (State.APPROVED, State.REJECTED, State.READY, State.ENCODED),
        State.DEDUPLICATION_FAILED: (State.DEDUPLICATION_IN_PROGRESS, State.ENCODING_IN_PROGRESS),
        State.APPROVED: (),
        State.REJECTED: (),
    }

    PROCESSABLE_STATES: Final[tuple[int, ...]] = (
        State.READY,
        State.ENCODED,
        State.ENCODING_FAILED,
        State.DEDUPLICATION_FAILED,
    )

    BLOCKING_STATES: Final[tuple[int, ...]] = (
        State.EMPTY,
        State.UPLOADING_IN_PROGRESS,
        State.READY,
        State.ENCODING_IN_PROGRESS,
        State.ENCODED,
        State.DEDUPLICATION_IN_PROGRESS,
        State.DEDUPLICATED,
    )

    id = models.UUIDField(primary_key=True, default=uuid4, help_text="Deduplication set id.")
    group = models.ForeignKey(DeduplicationSetGroup, on_delete=models.CASCADE, help_text="Deduplication set group.")
    name = models.CharField(
        max_length=128, unique=True, null=True, blank=True, db_index=True, help_text="Deduplication set name."
    )
    description = models.TextField(null=True, blank=True, help_text="Deduplication set description.")
    state = models.IntegerField(
        choices=State, default=State.EMPTY, db_column="state", help_text="Deduplication set state."
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
    log = models.JSONField(
        default=list,
        blank=True,
        help_text="Append-only audit log of encoding/deduplication attempts.",
    )

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
                condition=(
                    ~Q(state=ENCODING_FAILED_STATE)
                    & ~Q(state=DEDUPLICATION_FAILED_STATE)
                    & ~Q(state=APPROVED_STATE)
                    & ~Q(state=REJECTED_STATE)
                ),
                name="unique_active_deduplication_set_per_group",
            ),
        ]

    def __str__(self) -> str:
        return self.name or f"ID: {self.pk}"

    def duplicate_findings(self) -> QuerySet["Finding"]:
        return self.finding_set.filter(second_encoding__isnull=False)

    def clear_embeddings_data(self) -> None:
        self.encoding_set.update(embedding=None, embedding_status_code=None)
        self.finding_set.all().delete()

    def encodings_with_embeddings(self) -> QuerySet["Encoding"]:
        return self.encoding_set.filter(embedding__isnull=False)

    def encodings_without_embeddings(self) -> QuerySet["Encoding"]:
        return self.encoding_set.filter(embedding__isnull=True).exclude(
            embedding_status_code__in=EncodingErrorGroup.FACE_DETECT + EncodingErrorGroup.IMAGE_QUALITY
        )

    def set_state(self, state: State, error: Exception | None = None, force: bool = False) -> None:
        if not force:
            allowed = self.VALID_TRANSITIONS.get(self.state, ())
            if state not in allowed:
                raise ValueError(f"Invalid state transition: {self.State(self.state).label} -> {state.label}")
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
        BAD_IMAGE_QUALITY = 418, "image quality below threshold"
        MULTIPLE_FACES_DETECTED = 429, "multiple faces detected"
        GENERIC_ERROR = 500, "generic error"

    id = models.UUIDField(primary_key=True, default=uuid4, help_text="Encoding id.")
    deduplication_set = models.ForeignKey(DeduplicationSet, on_delete=models.CASCADE, help_text="Deduplication set.")
    reference_pk = models.CharField(max_length=REFERENCE_PK_LENGTH, help_text="External id of the encoding.")
    filename = models.FileField(
        storage=_images_storage,
        upload_to=encoding_image_upload_to,
        max_length=FILENAME_LENGTH,
        help_text="Image file backing this encoding (stored via the `images` Django storage alias).",
    )
    embedding = ArrayField(models.FloatField(), null=True, blank=True, help_text="Embedding vector.")
    embedding_status_code = models.IntegerField(
        choices=StatusCode, null=True, blank=True, help_text="Embedding status code."
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
        return f"Image {self.reference_pk}"


class EncodingErrorGroup:
    FACE_DETECT = (
        Encoding.StatusCode.FACE_NOT_ACCEPTED,
        Encoding.StatusCode.NO_FACE_DETECTED,
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
    config = models.JSONField(
        null=True,
        blank=True,
        help_text="Snapshot of the deduplication settings active when this finding was created.",
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
        first = self.first_encoding.reference_pk if self.first_encoding_id else "—"
        second = self.second_encoding.reference_pk if self.second_encoding_id else "—"
        return f"Finding({first}, {second})"
