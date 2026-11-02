"""Orchestration store for biographic deduplication.

Postgres owns the lifecycle; Elasticsearch only scores. Nothing in this module
imports the search library.
"""

from typing import Any, Final

from django.db import models, transaction
from django.db.models import Q
from django_celery_boost.models import CeleryTaskModel

from hope_dedup_engine.apps.api.models.deduplication import MAX_ERROR_LENGTH, REFERENCE_PK_LENGTH
from hope_dedup_engine.apps.api.models.jobs import GracefulJobCancellationError
from hope_dedup_engine.apps.biographic.const import PROCESS_DATASET_TASK
from hope_dedup_engine.apps.biographic.exceptions import InvalidTransitionError
from hope_dedup_engine.apps.biographic.schemas import PAYLOAD_VERSION

BUSINESS_AREA_LENGTH: Final[int] = 100
PROGRAM_CODE_LENGTH: Final[int] = 100
FULL_NAME_LENGTH: Final[int] = 255
NOTIFICATION_URL_LENGTH: Final[int] = 255
SCOPE_LENGTH: Final[int] = 16
STATE_LENGTH: Final[int] = 16

FULL_NAME_FIELD: Final[str] = "full_name"
BULK_CREATE_BATCH_SIZE: Final[int] = 1_000


class BiographicGroup(models.Model):
    """One business area and one program: the isolation unit for biographic dedup.

    Maps 1:1 to an Elasticsearch index. Owns the settings shared by every dataset
    submitted for the program, and the lock that serializes processing. Two programs
    in the same business area lock independently.
    """

    business_area = models.CharField(max_length=BUSINESS_AREA_LENGTH, db_index=True, help_text="Business area slug.")
    program_code = models.CharField(
        max_length=PROGRAM_CODE_LENGTH, db_index=True, help_text="Program code, as HOPE names it."
    )
    settings = models.JSONField(
        default=dict, null=True, blank=True, help_text="Settings common for all datasets in this group."
    )
    deleted = models.BooleanField(default=False, help_text="Whether this group was deleted.")
    processing_locked = models.BooleanField(
        default=False, help_text="Whether any biographic task is currently running for this program."
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business_area", "program_code"],
                name="unique_biographic_group",
            ),
        ]
        permissions = [
            ("release_processing_lock", "Can release processing lock"),
            ("rebuild_index", "Can rebuild index"),
        ]

    def __str__(self) -> str:
        return f"{self.business_area}:{self.program_code}"

    def acquire_processing_lock(self) -> bool:
        with transaction.atomic():
            group = BiographicGroup.objects.select_for_update().get(pk=self.pk)
            if group.processing_locked:
                return False
            group.processing_locked = True
            group.save(update_fields=["processing_locked"])
            self.processing_locked = True
            return True

    def release_processing_lock(self) -> None:
        self.processing_locked = False
        self.save(update_fields=["processing_locked"])


PENDING_STATE: Final[str] = "pending"
INDEXING_STATE: Final[str] = "indexing"
INDEXED_STATE: Final[str] = "indexed"
DEDUPLICATING_STATE: Final[str] = "deduplicating"
DEDUPLICATED_STATE: Final[str] = "deduplicated"
FAILED_STATE: Final[str] = "failed"
APPROVED_STATE: Final[str] = "approved"
REJECTED_STATE: Final[str] = "rejected"
CANCELED_STATE: Final[str] = "canceled"


class BiographicSet(models.Model):
    """A submitted dataset of people, and its position in the review lifecycle."""

    class State(models.TextChoices):
        PENDING = PENDING_STATE, "Pending"
        INDEXING = INDEXING_STATE, "Indexing"
        INDEXED = INDEXED_STATE, "Indexed"
        DEDUPLICATING = DEDUPLICATING_STATE, "Deduplicating"
        DEDUPLICATED = DEDUPLICATED_STATE, "Deduplicated"
        FAILED = FAILED_STATE, "Failed"
        APPROVED = APPROVED_STATE, "Approved"
        REJECTED = REJECTED_STATE, "Rejected"
        CANCELED = CANCELED_STATE, "Canceled"

    VALID_TRANSITIONS: Final[dict[str, tuple[str, ...]]] = {
        State.PENDING: (State.INDEXING, State.CANCELED),
        State.INDEXING: (State.INDEXED, State.FAILED),
        State.INDEXED: (State.DEDUPLICATING, State.FAILED),
        State.DEDUPLICATING: (State.DEDUPLICATED, State.FAILED),
        # A scored set may be scored again, from the admin, before it is decided.
        State.DEDUPLICATED: (State.APPROVED, State.REJECTED, State.DEDUPLICATING),
        State.FAILED: (State.INDEXING, State.CANCELED),
        State.APPROVED: (),
        State.REJECTED: (),
        State.CANCELED: (),
    }

    # Holding the program's single processing slot: being indexed or scored, or
    # scored and waiting for the client to approve or reject. Pending and failed
    # sets are only a queue, so a client can keep submitting while one is in flight.
    ACTIVE_STATES: Final[tuple[str, ...]] = (INDEXING_STATE, INDEXED_STATE, DEDUPLICATING_STATE, DEDUPLICATED_STATE)

    PROCESSABLE_STATES: Final[tuple[str, ...]] = (PENDING_STATE, FAILED_STATE)
    CANCELABLE_STATES: Final[tuple[str, ...]] = (PENDING_STATE, FAILED_STATE)
    FINDINGS_STATES: Final[tuple[str, ...]] = (DEDUPLICATED_STATE, APPROVED_STATE)

    group = models.ForeignKey(
        BiographicGroup, on_delete=models.CASCADE, related_name="sets", help_text="Biographic group."
    )
    state = models.CharField(
        max_length=STATE_LENGTH,
        choices=State,
        default=State.PENDING,
        db_index=True,
        help_text="Biographic set state.",
    )
    error = models.CharField(max_length=MAX_ERROR_LENGTH, null=True, blank=True, help_text="Why the last run failed.")
    notification_url = models.CharField(
        max_length=NOTIFICATION_URL_LENGTH, null=True, blank=True, help_text="Pinged on every state change a run makes."
    )
    notify = models.BooleanField(default=True, help_text="Whether to send notifications about state changes.")
    log = models.JSONField(default=list, blank=True, help_text="Append-only audit log of processing attempts.")
    # Set by approve, reject and cancel-from-failed; cleared when Elasticsearch has
    # the matching status. Left set, the next run in the program reconciles it.
    search_sync_pending = models.BooleanField(
        default=False, help_text="Whether the set's decision still has to reach Elasticsearch."
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date and time when this set was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="Date and time when this set was last updated.")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group"],
                condition=Q(state__in=(INDEXING_STATE, INDEXED_STATE, DEDUPLICATING_STATE, DEDUPLICATED_STATE)),
                name="unique_active_biographic_set_per_group",
            ),
        ]
        permissions = [
            ("send_notification", "Can send notification"),
            ("process_indexing", "Can index records"),
            ("process_deduplicate", "Can find duplicates"),
        ]

    def __str__(self) -> str:
        return f"ID: {self.pk}"

    def set_state(self, state: "BiographicSet.State", error: str | None = None, force: bool = False) -> None:
        if not force:
            allowed = self.VALID_TRANSITIONS.get(self.state, ())
            if state not in allowed:
                raise ValueError(f"Invalid state transition: {self.State(self.state).label} -> {state.label}")
        self.state = state.value
        self.error = error[:MAX_ERROR_LENGTH] if error else None
        self.save(update_fields=["state", "error", "updated_at"])

    def transition(
        self,
        allowed: tuple[str, ...],
        target: "BiographicSet.State",
        verb: str,
        *,
        search_sync_pending: bool = False,
    ) -> None:
        """Move to `target`, refusing unless the set is in one of `allowed`.

        The row is locked first, so two concurrent requests cannot both pass the
        check. `verb` names the action in the error, for the client. A decision
        passes `search_sync_pending=True` so the flag and the state commit together.
        """
        with transaction.atomic():
            locked = BiographicSet.objects.select_for_update().get(pk=self.pk)
            if locked.state not in allowed:
                raise InvalidTransitionError(f"Cannot {verb} set in '{locked.get_state_display()}' state.")
            if search_sync_pending:
                locked.search_sync_pending = True
                locked.save(update_fields=["search_sync_pending"])
            locked.set_state(target)
        self.refresh_from_db(fields=["state", "error", "search_sync_pending", "updated_at"])

    def append_log(self, entry: dict[str, Any]) -> None:
        self.log.append(entry)
        self.save(update_fields=["log"])


class BiographicJob(CeleryTaskModel):
    """One processing run of a set, tracked by django-celery-boost.

    The row is what the admin queues, watches and terminates. The set's state
    machine, not the job, says whether a run may start.
    """

    class Mode(models.TextChoices):
        FULL = "full", "Index and search"
        INDEX = "index", "Index only"
        SEARCH = "search", "Search only"

    dataset = models.ForeignKey(
        BiographicSet, on_delete=models.CASCADE, related_name="jobs", help_text="Set this run processes."
    )
    mode = models.CharField(
        max_length=16,
        choices=Mode,
        default=Mode.FULL,
        help_text="Which steps the run performs. Only an administrator starts a partial run.",
    )
    config_overrides = models.JSONField(
        default=dict, blank=True, help_text="Settings the client overrode for this run."
    )

    celery_task_name = PROCESS_DATASET_TASK

    def __str__(self) -> str:
        return f"Job {self.pk} for set {self.dataset_id}"

    def ensure_not_cancelled(self) -> None:
        if self.is_termination_requested:
            raise GracefulJobCancellationError(f"Cancellation requested for job #{self.pk}")


class BiographicRecordQuerySet(models.QuerySet["BiographicRecord"]):
    def upsert_batch(self, dataset: BiographicSet, rows: list[dict[str, Any]]) -> int:
        """Insert `rows` into `dataset`, replacing any `reference_pk` already there.

        Each row is `{"reference_pk": ..., "payload": {...}}`, already validated.
        Returns the number of rows written.
        """
        records = [
            BiographicRecord(
                dataset=dataset,
                reference_pk=row["reference_pk"],
                payload=row["payload"],
                full_name=(row["payload"].get(FULL_NAME_FIELD) or "")[:FULL_NAME_LENGTH],
                payload_version=PAYLOAD_VERSION,
            )
            for row in rows
        ]
        self.bulk_create(
            records,
            batch_size=BULK_CREATE_BATCH_SIZE,
            update_conflicts=True,
            unique_fields=["dataset", "reference_pk"],
            update_fields=["payload", "full_name", "payload_version"],
        )
        return len(records)


class BiographicRecord(models.Model):
    """One person submitted for deduplication."""

    dataset = models.ForeignKey(
        BiographicSet, on_delete=models.CASCADE, related_name="records", help_text="Set this person was submitted in."
    )
    reference_pk = models.CharField(
        max_length=REFERENCE_PK_LENGTH,
        db_index=True,
        help_text="Country Workspace individual id, or the HOPE UUID for migrated data.",
    )
    full_name = models.CharField(
        max_length=FULL_NAME_LENGTH,
        blank=True,
        db_index=True,
        help_text="Copied from the payload so the admin can search names. Never used for matching.",
    )
    payload = models.JSONField(help_text="Scoreable biographic fields.")
    payload_version = models.PositiveSmallIntegerField(default=PAYLOAD_VERSION, help_text="Payload schema version.")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date and time when this record was created.")

    objects = BiographicRecordQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["dataset", "reference_pk"],
                name="unique_biographic_record_per_set",
            ),
        ]

    def __str__(self) -> str:
        return self.reference_pk


class BiographicFinding(models.Model):
    """One scored pair: a record, and the person Elasticsearch matched it against."""

    class Scope(models.TextChoices):
        BATCH = "batch", "Batch"
        POPULATION = "population", "Population"

    # Denormalized from `record`: every read is "all findings for this set", and the
    # join costs more than the column.
    dataset = models.ForeignKey(
        BiographicSet, on_delete=models.CASCADE, related_name="+", help_text="Set the scored record belongs to."
    )
    record = models.ForeignKey(
        BiographicRecord, on_delete=models.CASCADE, related_name="findings", help_text="Record that was scored."
    )
    # Not a foreign key: a population match belongs to another set, possibly migrated from HOPE.
    matched_reference_pk = models.CharField(
        max_length=REFERENCE_PK_LENGTH, help_text="Reference pk of the matched person."
    )
    matched_full_name = models.CharField(
        max_length=FULL_NAME_LENGTH, blank=True, help_text="Full name of the matched person."
    )
    matched_birth_date = models.DateField(null=True, blank=True, help_text="Birth date of the matched person.")
    score = models.FloatField(help_text="Similarity score returned by Elasticsearch.")
    proximity_to_score = models.FloatField(
        help_text="Score minus the duplicate threshold that was in force when this finding was created."
    )
    scope = models.CharField(
        max_length=SCOPE_LENGTH,
        choices=Scope,
        help_text="Whether the match came from the same set or from the approved population.",
    )
    config = models.JSONField(
        null=True, blank=True, help_text="Snapshot of the biographic settings active when this finding was created."
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date and time when this finding was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="Date and time when this finding was updated.")

    class Meta:
        indexes = [
            models.Index(fields=["dataset", "-score", "-id"], name="biographic_finding_order_idx"),
        ]
        constraints = [
            # A person indexed by two approved sets is two documents with one
            # reference_pk; the run keeps the best hit per person and scope.
            models.UniqueConstraint(
                fields=["record", "matched_reference_pk", "scope"],
                name="unique_biographic_finding",
            ),
        ]

    def __str__(self) -> str:
        return f"Finding({self.record.reference_pk}, {self.matched_reference_pk})"
