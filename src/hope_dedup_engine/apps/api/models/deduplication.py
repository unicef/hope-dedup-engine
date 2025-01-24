from typing import Any, Final, override
from uuid import uuid4

from django.conf import settings
from django.db import models, transaction

from hope_dedup_engine.apps.security.models import ExternalSystem
from hope_dedup_engine.types import (
    Embedding,
    EntityEmbedding,
    EntityEmbeddingError,
    Filename,
    Finding,
    IgnoredPair,
    ImageEmbedding,
    ImageEmbeddingError,
    Score,
)

REFERENCE_PK_LENGTH: Final[int] = 100


class DeduplicationSet(models.Model):
    """
    Bucket for entries we want to deduplicate
    """

    class State(models.IntegerChoices):
        CLEAN = 0, "Clean"  # Deduplication set is created or already processed
        DIRTY = (
            1,
            "Dirty",
        )  # Images are added to deduplication set, but not yet processed

    id = models.UUIDField(primary_key=True, default=uuid4)
    name = models.CharField(
        max_length=128, unique=True, null=True, blank=True, db_index=True
    )
    description = models.TextField(null=True, blank=True)
    reference_pk = models.CharField(max_length=REFERENCE_PK_LENGTH)  # source_id
    state = models.IntegerField(
        choices=State.choices,
        default=State.CLEAN,
        db_column="state",
    )
    deleted = models.BooleanField(null=False, blank=False, default=False)
    external_system = models.ForeignKey(ExternalSystem, on_delete=models.CASCADE)
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

    # TODO: rename to embeddings as it's more correct term
    encodings = models.JSONField(
        null=True, blank=True, default=dict
    )  # {file1: embedding1, file2: embedding2, ...}

    encoding_errors = models.JSONField(
        null=True, blank=True, default=dict
    )  # {file1: embedding_error1, file2: embedding_error2, ...}

    def __str__(self) -> str:
        return self.name or f"ID: {self.pk}"

    def get_encodings(self) -> dict[Filename, Embedding]:
        return self.encodings

    def get_findings(self) -> list[Finding]:
        return list(
            self.finding_set.values_list(
                "first_reference_pk", "second_reference_pk", "score"
            )
        )

    def get_ignored_pairs(self) -> list[IgnoredPair]:
        return list(
            self.ignoredreferencepkpair_set.values_list("first", "second")
        ) + list(self.ignoredfilenamepair_set.values_list("first", "second"))

    def update_encodings(self, encodings: list[ImageEmbedding]) -> None:
        with transaction.atomic():
            fresh_self: DeduplicationSet = (
                DeduplicationSet.objects.select_for_update().get(pk=self.pk)
            )
            fresh_self.encodings.update(encodings)
            fresh_self.save()

    def update_encoding_errors(self, errors: list[ImageEmbeddingError]) -> None:
        with transaction.atomic():
            fresh_self: DeduplicationSet = (
                DeduplicationSet.objects.select_for_update().get(pk=self.pk)
            )
            fresh_self.encoding_errors.update(errors)
            fresh_self.save()

    def update_findings(
        self, findings: list[tuple[EntityEmbedding, EntityEmbedding, Score]]
    ) -> None:
        Finding.objects.bulk_create(
            [
                Finding(
                    deduplication_set=self,
                    first_reference_pk=first_reference_pk,
                    second_reference_pk=second_reference_pk,
                    score=score,
                )
                for (first_reference_pk, _), (second_reference_pk, _), score in findings
            ],
            ignore_conflicts=True,
        )

    def update_finding_errors(
        self, encoding_errors: list[EntityEmbeddingError]
    ) -> None:
        Finding.objects.bulk_create(
            [
                Finding(
                    deduplication_set=self,
                    first_reference_pk=reference_pk,
                    second_reference_pk=error.name,
                    error=error.value,
                )
                for reference_pk, error in encoding_errors
            ],
            ignore_conflicts=True,
        )


class Image(models.Model):
    """
    # TODO: rename to Entity/Entry
    """

    id = models.UUIDField(primary_key=True, default=uuid4)
    deduplication_set = models.ForeignKey(DeduplicationSet, on_delete=models.CASCADE)
    reference_pk = models.CharField(max_length=REFERENCE_PK_LENGTH)
    filename = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)


class Finding(models.Model):
    """
    Couple of finding entities
    """

    # class ErrorCode(models.IntegerChoices):
    #     GENERIC_ERROR = 999
    #     NO_FACE_DETECTED = 998
    #     MULTIPLE_FACES_DETECTED = 997
    #     NO_FILE_FOUND = 996

    deduplication_set = models.ForeignKey(DeduplicationSet, on_delete=models.CASCADE)
    first_reference_pk = models.CharField(
        max_length=REFERENCE_PK_LENGTH, verbose_name="First reference"
    )
    second_reference_pk = models.CharField(
        max_length=REFERENCE_PK_LENGTH, verbose_name="Second reference"
    )
    score = models.FloatField(default=0, validators=[], verbose_name="Similarity Score")
    error = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = (
            "deduplication_set",
            "first_reference_pk",
            "second_reference_pk",
        )


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


class IgnoredFilenamePair(IgnoredPair):
    first = models.CharField(max_length=REFERENCE_PK_LENGTH)
    second = models.CharField(max_length=REFERENCE_PK_LENGTH)

    class Meta:
        unique_together = UNIQUE_FOR_IGNORED_PAIR
