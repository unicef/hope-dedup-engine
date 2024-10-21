from typing import Any, Final, override
from uuid import uuid4

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from hope_dedup_engine.apps.api.utils.notification import send_notification
from hope_dedup_engine.apps.security.models import ExternalSystem

REFERENCE_PK_LENGTH: Final[int] = 100


class Config(models.Model):
    face_distance_threshold = models.FloatField(
        null=True,
        validators=[MinValueValidator(0.1), MaxValueValidator(1.0)],
    )

    def __str__(self) -> str:
        return " | ".join(
            f"{field.name}: {getattr(self, field.name)}"
            for field in self._meta.fields
            if field.name not in ("id",)
        )


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
            send_notification(self.notification_url)

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
