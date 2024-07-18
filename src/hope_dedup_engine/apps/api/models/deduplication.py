from typing import Any, override
from uuid import uuid4

from django.conf import settings
from django.db import models

from hope_dedup_engine.apps.security.models import ExternalSystem

REFERENCE_PK_LENGTH = 100


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
        PROCESSING = 2, "Processing"  # Images are being processed
        ERROR = 3, "Error"  # Error occurred

    id = models.UUIDField(primary_key=True, default=uuid4)
    name = models.CharField(max_length=100)
    reference_pk = models.CharField(max_length=REFERENCE_PK_LENGTH)  # source_id
    state = models.IntegerField(
        choices=State.choices,
        default=State.CLEAN,
    )
    deleted = models.BooleanField(null=False, blank=False, default=False)
    external_system = models.ForeignKey(ExternalSystem, on_delete=models.CASCADE)
    error = models.CharField(max_length=255, null=True, blank=True)
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


class Duplicate(models.Model):
    """
    Couple of similar entities
    """

    deduplication_set = models.ForeignKey(DeduplicationSet, on_delete=models.CASCADE)
    first_reference_pk = models.CharField(max_length=REFERENCE_PK_LENGTH)  # from hope
    first_filename = models.CharField(max_length=255)
    second_reference_pk = models.CharField(max_length=REFERENCE_PK_LENGTH)  # from hope
    second_filename = models.CharField(max_length=255)
    score = models.FloatField()


class IgnoredKeyPair(models.Model):
    deduplication_set = models.ForeignKey(DeduplicationSet, on_delete=models.CASCADE)
    first_reference_pk = models.CharField(max_length=REFERENCE_PK_LENGTH)
    second_reference_pk = models.CharField(max_length=REFERENCE_PK_LENGTH)

    class Meta:
        unique_together = (
            "deduplication_set",
            "first_reference_pk",
            "second_reference_pk",
        )

    @override
    def save(self, **kwargs: Any) -> None:
        self.first_reference_pk, self.second_reference_pk = sorted(
            (self.first_reference_pk, self.second_reference_pk)
        )
        super().save(**kwargs)
