from typing import Any, Final, override
from uuid import uuid4

from django.conf import settings
from django.db import models

import requests
import sentry_sdk

from hope_dedup_engine.apps.security.models import ExternalSystem

REFERENCE_PK_LENGTH: Final[int] = 100
REQUEST_TIMEOUT: Final[int] = 5


class Config(models.Model):
    face_distance_threshold = models.FloatField(null=True)


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
    name = models.CharField(
        max_length=128, unique=True, null=True, blank=True, db_index=True
    )
    description = models.TextField(null=True, blank=True)
    reference_pk = models.CharField(max_length=REFERENCE_PK_LENGTH)  # source_id
    state_value = models.IntegerField(
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
    config = models.OneToOneField(Config, null=True, on_delete=models.SET_NULL)

    @property
    def state(self) -> State:
        return self.State(self.state_value)

    @state.setter
    def state(self, value: State) -> None:
        if value != self.state_value or value == self.State.CLEAN:
            self.state_value = value
            if self.notification_url:
                self.send_notification()

    def send_notification(self) -> None:
        try:
            with requests.get(self.notification_url, timeout=REQUEST_TIMEOUT) as r:
                r.raise_for_status
        except requests.RequestException as e:
            sentry_sdk.capture_exception(e)

    def __str__(self) -> str:
        return f"ID: {self.pk}" if not self.name else f"{self.name}"


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
    second_reference_pk = models.CharField(max_length=REFERENCE_PK_LENGTH)  # from hope
    score = models.FloatField(default=0)


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
