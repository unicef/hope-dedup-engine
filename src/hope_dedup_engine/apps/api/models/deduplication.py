import traceback
from typing import Any, Final, override
from uuid import uuid4

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Exists, OuterRef

from hope_dedup_engine.apps.security.models import System
from hope_dedup_engine.type_aliases import EncodingType, FindingType, IgnoredPairType

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
    state = models.IntegerField(
        choices=State.choices,
        default=State.READY,
        db_column="state",
    )
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

    def get_encodings(self) -> EncodingType:
        return {encoding.filename: encoding.data for encoding in self.encoding_set.all()}

    def filenames_without_encodings(self):
        enc_any = Encoding.objects.filter(filename=OuterRef("filename"))
        return (
            self.image_set.annotate(has_enc=Exists(enc_any))
            .filter(has_enc=False)
            .order_by("filename")
            .values_list("filename", flat=True)
            .distinct()
        )

    def get_findings(self) -> FindingType:
        return list(self.finding_set.values_list("first_reference_pk", "second_reference_pk", "score"))

    def get_ignored_pairs(self) -> IgnoredPairType:
        return list(self.ignoredreferencepkpair_set.values_list("first", "second")) + list(
            self.ignoredfilenamepair_set.values_list("first", "second")
        )

    def update_encodings(self, encodings: EncodingType) -> None:
        # sort to prevent deadlock
        filenames = sorted(encodings.keys())
        Encoding.objects.bulk_create(
            [Encoding(deduplication_set=self, filename=filename, data=encodings[filename]) for filename in filenames],
            update_conflicts=True,
            update_fields=["data"],
            unique_fields=["deduplication_set", "filename"],
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

    def __str__(self) -> str:
        return f"Image {self.filename}"


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
    status_code = models.IntegerField(choices=Image.StatusCode.choices, default=Image.StatusCode.DEDUPLICATE_SUCCESS)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["deduplication_set", "-updated_at", "-id"], name="finding_order_idx"),
        ]
        unique_together = (
            "deduplication_set",
            "first_reference_pk",
            "second_reference_pk",
        )

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
        unique_together = UNIQUE_FOR_IGNORED_PAIR

    def __str__(self) -> str:
        return f"IgnoredReferencePkPair({self.first}, {self.second})"


class IgnoredFilenamePair(IgnoredPair):
    first = models.CharField(max_length=REFERENCE_PK_LENGTH)
    second = models.CharField(max_length=REFERENCE_PK_LENGTH)

    class Meta:
        unique_together = UNIQUE_FOR_IGNORED_PAIR

    def __str__(self) -> str:
        return f"IgnoredFilenamePair({self.first}, {self.second})"


class Encoding(models.Model):
    deduplication_set = models.ForeignKey(DeduplicationSet, on_delete=models.CASCADE)
    filename = models.CharField(max_length=FILENAME_LENGTH)
    data = models.JSONField()

    class Meta:
        unique_together = (
            "deduplication_set",
            "filename",
        )
        indexes = [models.Index(fields=["filename"])]

    def __str__(self) -> str:
        return f"Encoding({self.filename})"
