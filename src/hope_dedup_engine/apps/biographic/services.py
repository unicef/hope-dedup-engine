from typing import Any

from celery import current_app
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from hope_dedup_engine.apps.api.exceptions import ConflictError
from hope_dedup_engine.apps.biographic.config import resolve_config
from hope_dedup_engine.apps.biographic.contracts import PAYLOAD_VERSION
from hope_dedup_engine.apps.biographic.models import (
    BiographicFinding,
    BiographicGroup,
    BiographicRecord,
    BiographicSet,
)
from hope_dedup_engine.apps.biographic.serializers import full_name_from_payload

INDEX_RECORDS_TASK = "apps.biographic.tasks.index_biographic_records"
PROCESS_DATASET_TASK = "apps.biographic.tasks.process_biographic_dataset"
UPDATE_STATUS_TASK = "apps.biographic.tasks.update_biographic_status"

_ACTIVE_DATASET = "Another dataset is already active for this program."
_LOCK_HELD = "Another task is already running for this program."
_CONFIG_OBJECT = "Config must be an object."
_STATUS_CODE = "status_code must be duplicate."
_DATETIME = "{name} must be an ISO 8601 datetime."


class BiographicDatasetService:
    """Persistence, locking, and task enqueueing for one biographic dataset."""

    def get_or_create_group(self, business_area: str, program_id: str) -> BiographicGroup:
        """Create the program group from the URL the first time a client calls it."""
        try:
            group, _created = BiographicGroup.objects.get_or_create(
                business_area=business_area,
                program_id=program_id,
            )
        except IntegrityError:
            group = BiographicGroup.objects.get(business_area=business_area, program_id=program_id)
        return group

    def queue_task(self, task_name: str, *args: Any, **kwargs: Any) -> None:
        """Enqueue a service task by dotted path. The service issue owns the body."""
        current_app.send_task(task_name, args=list(args), kwargs=kwargs)

    def create_dataset(self, group: BiographicGroup, records: list[dict[str, Any]]) -> BiographicSet:
        """Insert the dataset and its people in one transaction."""
        with transaction.atomic():
            dataset = BiographicSet.objects.create(group=group, state=BiographicSet.State.PENDING)
            created_at = timezone.now()
            BiographicRecord.objects.bulk_create(
                [
                    BiographicRecord(
                        dataset=dataset,
                        reference_pk=record["reference_pk"],
                        payload=record["payload"],
                        full_name=full_name_from_payload(record["payload"]),
                        payload_version=PAYLOAD_VERSION,
                        created_at=created_at,
                    )
                    for record in records
                ]
            )
        return dataset

    def config_overrides(
        self,
        request: Request,
        dataset: BiographicSet,
    ) -> tuple[dict[str, Any] | None, Response | None]:
        if not isinstance(request.data, dict) or "config" not in request.data:
            return None, None
        raw = request.data["config"]
        if not isinstance(raw, dict):
            return None, Response({"detail": _CONFIG_OBJECT}, status=status.HTTP_400_BAD_REQUEST)
        try:
            resolve_config(dataset, raw)
        except ValueError as exc:
            return None, Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return raw, None

    def lock_dataset(self, dataset: BiographicSet) -> None:
        """Reject a second active dataset, then hold the program lock."""
        with transaction.atomic():
            group = BiographicGroup.objects.select_for_update().get(pk=dataset.group_id)
            if group.processing_locked:
                raise ConflictError(_LOCK_HELD)
            active = BiographicSet.objects.filter(
                group=group,
                state__in=BiographicSet.PROCESS_BLOCKING_STATES,
            ).exclude(pk=dataset.pk)
            if active.exists():
                raise ConflictError(_ACTIVE_DATASET)
            group.processing_locked = True
            group.save(update_fields=["processing_locked"])
            dataset.group.processing_locked = True

    def filter_findings(
        self,
        dataset: BiographicSet,
        request: Request,
    ) -> tuple[list[BiographicFinding], Response | None]:
        findings = BiographicFinding.objects.filter(record__dataset=dataset).select_related("record")
        status_code = request.query_params.get("status_code")
        if status_code:
            if status_code not in BiographicFinding.StatusCode.values:
                return [], Response({"detail": _STATUS_CODE}, status=status.HTTP_400_BAD_REQUEST)
            findings = findings.filter(status_code=status_code)
        updated_after, error = self._parsed_datetime(request, "updated_after")
        if error is not None:
            return [], error
        if updated_after is not None:
            findings = findings.filter(updated_at__gte=updated_after)
        updated_before, error = self._parsed_datetime(request, "updated_before")
        if error is not None:
            return [], error
        if updated_before is not None:
            findings = findings.filter(updated_at__lte=updated_before)
        return list(findings.order_by("-updated_at", "id")), None

    def finding_payload(self, finding: BiographicFinding) -> dict[str, Any]:
        return {
            "first": {"reference_pk": finding.record.reference_pk},
            "second": {"reference_pk": finding.matched_reference_pk},
            "score": finding.score,
            "status_code": finding.status_code,
            "config": finding.config,
            "updated_at": finding.updated_at,
            "proximity_to_score": finding.proximity_to_score,
        }

    def transition(self, dataset: BiographicSet | Response, state: str) -> Response:
        if isinstance(dataset, Response):
            return dataset
        try:
            dataset.set_state(state)
        except ValueError as exc:
            raise ConflictError(str(exc)) from exc
        dataset.group.release_processing_lock()
        self.queue_task(UPDATE_STATUS_TASK, dataset.pk, dataset.state)
        return Response(status=status.HTTP_200_OK)

    def _parsed_datetime(self, request: Request, name: str) -> tuple[Any, Response | None]:
        raw = request.query_params.get(name)
        if raw in (None, ""):
            return None, None
        parsed = parse_datetime(raw)
        if parsed is None:
            return None, Response({"detail": _DATETIME.format(name=name)}, status=status.HTTP_400_BAD_REQUEST)
        return parsed, None
