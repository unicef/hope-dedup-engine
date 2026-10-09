from typing import Any, Final

from django.db import models, transaction

from hope_dedup_engine.apps.api.models.deduplication import REFERENCE_PK_LENGTH
from hope_dedup_engine.apps.biographic.contracts import PAYLOAD_VERSION, MatchScope

FULL_NAME_LENGTH: Final[int] = 255
STATE_LENGTH: Final[int] = 32


class BiographicGroup(models.Model):
    """One business area and one program. Maps 1:1 to an Elasticsearch index."""

    id = models.BigAutoField(primary_key=True)
    business_area = models.CharField(max_length=100, db_index=True, help_text="Business area slug.")
    program_id = models.CharField(max_length=100, db_index=True, help_text="Program id.")
    name = models.CharField(max_length=128, null=True, blank=True, help_text="Optional group name.")
    settings = models.JSONField(default=dict, blank=True, help_text="Settings shared by datasets in this group.")
    processing_locked = models.BooleanField(
        default=False,
        help_text="Whether a deduplication task is currently running for this program.",
    )
    deleted = models.BooleanField(default=False, help_text="Whether this group was deleted.")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business_area", "program_id"],
                name="unique_biographic_group_business_area_program",
            ),
        ]
        permissions = [
            ("release_processing_lock", "Can release processing lock"),
        ]

    def __str__(self) -> str:
        label = self.name or f"{self.business_area}:{self.program_id}"
        return str(label)

    def acquire_processing_lock(self) -> bool:
        """Lock this program. A lock on one program does not lock its business area."""
        with transaction.atomic():
            group = BiographicGroup.objects.select_for_update().get(pk=self.pk)
            if group.processing_locked:
                return False
            group.processing_locked = True
            group.save(update_fields=["processing_locked"])
            self.processing_locked = True
            return True

    def release_processing_lock(self) -> None:
        """Release this program's processing lock."""
        with transaction.atomic():
            group = BiographicGroup.objects.select_for_update().get(pk=self.pk)
            group.processing_locked = False
            group.save(update_fields=["processing_locked"])
            self.processing_locked = False


class BiographicSetState(models.TextChoices):
    PENDING = "pending", "Pending"
    DEDUPLICATING = "deduplicating", "Deduplicating"
    DEDUPLICATED = "deduplicated", "Deduplicated"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


def _active_states() -> tuple[str, ...]:
    """States that occupy the one active slot per group.

    Pending is excluded so a client can submit the next dataset while another
    is still pending. Process returns 409 when another set is pending,
    deduplicating, or deduplicated.
    """
    return (BiographicSetState.DEDUPLICATING.value, BiographicSetState.DEDUPLICATED.value)


class BiographicSet(models.Model):
    """A submitted dataset. Business area and program live on the group."""

    State = BiographicSetState

    PROCESS_BLOCKING_STATES: Final[tuple[str, ...]] = (
        State.PENDING,
        State.DEDUPLICATING,
        State.DEDUPLICATED,
    )
    VALID_TRANSITIONS: Final[dict[str, tuple[str, ...]]] = {
        State.PENDING: (State.DEDUPLICATING,),
        State.DEDUPLICATING: (State.DEDUPLICATED,),
        State.DEDUPLICATED: (State.APPROVED, State.REJECTED),
        State.APPROVED: (),
        State.REJECTED: (),
    }
    FINDINGS_STATES: Final[tuple[str, ...]] = (State.DEDUPLICATED, State.APPROVED)

    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(
        BiographicGroup,
        on_delete=models.CASCADE,
        related_name="sets",
        help_text="Program group this dataset belongs to.",
    )
    state = models.CharField(
        max_length=STATE_LENGTH,
        choices=State,
        default=State.PENDING,
        db_index=True,
        help_text="Dataset state.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group"],
                condition=models.Q(state__in=_active_states()),
                name="unique_active_biographic_set_per_group",
            ),
        ]

    def __str__(self) -> str:
        return f"Biographic set {self.pk} ({self.state})"

    @classmethod
    def active_states(cls) -> tuple[str, ...]:
        """Return states that occupy the one active slot per group."""
        return _active_states()

    def set_state(self, state: str) -> None:
        """Move to ``state`` or raise ValueError when the transition is not allowed."""
        try:
            target = self.State(state)
        except ValueError as exc:
            raise ValueError(f"Unknown state: {state}") from exc
        current = self.State(self.state)
        allowed = self.VALID_TRANSITIONS.get(current, ())
        if target not in allowed:
            raise ValueError(f"Invalid state transition: {current.label} -> {target.label}")
        self.state = target
        self.save(update_fields=["state"])


class BiographicRecord(models.Model):
    """One person. Scoreable fields live in ``payload``."""

    id = models.BigAutoField(primary_key=True)
    dataset = models.ForeignKey(
        BiographicSet,
        on_delete=models.CASCADE,
        related_name="records",
        help_text="Dataset this person belongs to.",
    )
    reference_pk = models.CharField(
        max_length=REFERENCE_PK_LENGTH,
        help_text="Country Workspace individual ID, or a HOPE UUID for migrated data.",
    )
    full_name = models.CharField(
        max_length=FULL_NAME_LENGTH,
        blank=True,
        db_index=True,
        help_text="Denormalized from the payload for admin search. Never used for matching.",
    )
    payload = models.JSONField(help_text="Scoreable biographic fields.")
    payload_version = models.PositiveSmallIntegerField(
        default=PAYLOAD_VERSION,
        help_text="Payload schema version.",
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date and time when this record was created.")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["dataset", "reference_pk"],
                name="unique_biographic_record_reference_pk_per_dataset",
            ),
        ]

    def __str__(self) -> str:
        return self.reference_pk

    def save(self, *args: Any, **kwargs: Any) -> None:
        from hope_dedup_engine.apps.biographic.serializers import (  # noqa: PLC0415
            full_name_from_payload,
            stored_payload_for_model,
        )

        self.payload = stored_payload_for_model(self.payload)
        self.full_name = full_name_from_payload(self.payload)
        super().save(*args, **kwargs)


class BiographicFinding(models.Model):
    """One duplicate pair. The match may live in another dataset, so it is not a foreign key."""

    class Scope(models.TextChoices):
        BATCH = MatchScope.BATCH.value, "Batch"
        POPULATION = MatchScope.POPULATION.value, "Population"

    class StatusCode(models.TextChoices):
        DUPLICATE = "duplicate", "Duplicate"

    id = models.BigAutoField(primary_key=True)
    record = models.ForeignKey(
        BiographicRecord,
        on_delete=models.CASCADE,
        related_name="findings",
        help_text="Person this match was found for.",
    )
    matched_reference_pk = models.CharField(
        max_length=REFERENCE_PK_LENGTH,
        help_text=(
            "Reference id of the matched person. Not a foreign key: the match may belong "
            "to another dataset or be a migrated HOPE UUID."
        ),
    )
    score = models.FloatField(help_text="Match score.")
    proximity_to_score = models.FloatField(help_text="Score minus the duplicate threshold.")
    status_code = models.CharField(
        max_length=STATE_LENGTH,
        choices=StatusCode,
        default=StatusCode.DUPLICATE,
        help_text="Duplicate. Not a biometric face status code.",
    )
    scope = models.CharField(
        max_length=STATE_LENGTH,
        choices=Scope,
        help_text="Batch or approved-population match. Used for abort counts, not returned to HOPE.",
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Snapshot of the settings used when this finding was created.",
    )
    updated_at = models.DateTimeField(auto_now=True, help_text="Date and time when this finding was updated.")

    def __str__(self) -> str:
        return f"{self.record.reference_pk} -> {self.matched_reference_pk}"
