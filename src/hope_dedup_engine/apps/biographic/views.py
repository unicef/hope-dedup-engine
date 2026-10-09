from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from hope_api_auth.views import TokenRequiredView
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from hope_dedup_engine.apps.api.exceptions import ConflictError
from hope_dedup_engine.apps.api.grant import Grant
from hope_dedup_engine.apps.biographic.models import BiographicGroup, BiographicSet
from hope_dedup_engine.apps.biographic.serializers import parse_dataset_records
from hope_dedup_engine.apps.biographic.services import (
    INDEX_RECORDS_TASK,
    PROCESS_DATASET_TASK,
    BiographicDatasetService,
)

_SLUG_LENGTH = 100
_SLUG_TOO_LONG = "Business area and program id must be at most 100 characters."
_DUPLICATE_REFERENCE_PK = "Duplicate reference_pk."
_CANNOT_PROCESS = "Cannot process a dataset in '{state}' state."
_FINDINGS_UNAVAILABLE = "Findings are available only for deduplicated or approved datasets."

service = BiographicDatasetService()


class BiographicAPIView(TokenRequiredView):
    permission = Grant.API_BIOGRAPHIC

    def get_group(self) -> BiographicGroup | Response:
        business_area = self.kwargs["business_area_slug"]
        program_id = self.kwargs["program_id"]
        if len(business_area) > _SLUG_LENGTH or len(program_id) > _SLUG_LENGTH:
            return Response({"detail": _SLUG_TOO_LONG}, status=status.HTTP_400_BAD_REQUEST)
        return service.get_or_create_group(business_area, program_id)

    def get_dataset(self) -> BiographicSet | Response:
        group = self.get_group()
        if isinstance(group, Response):
            return group
        return get_object_or_404(BiographicSet, pk=self.kwargs["dataset_id"], group=group)


class DatasetCreateView(BiographicAPIView):
    def post(self, request: Request, business_area_slug: str, program_id: str) -> Response:
        group = self.get_group()
        if isinstance(group, Response):
            return group
        records, errors = parse_dataset_records(request.data)
        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)
        try:
            dataset = service.create_dataset(group, records)
        except IntegrityError:
            return Response(
                {"errors": [{"index": None, "field": "reference_pk", "message": _DUPLICATE_REFERENCE_PK}]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        service.queue_task(INDEX_RECORDS_TASK, dataset.pk)
        return Response(
            {"dataset_id": dataset.pk, "status": BiographicSet.State.PENDING},
            status=status.HTTP_201_CREATED,
        )


class DatasetProcessView(BiographicAPIView):
    def post(self, request: Request, business_area_slug: str, program_id: str, dataset_id: int) -> Response:
        dataset = self.get_dataset()
        if isinstance(dataset, Response):
            return dataset
        if dataset.state != BiographicSet.State.PENDING:
            raise ConflictError(_CANNOT_PROCESS.format(state=dataset.state))
        overrides, error = service.config_overrides(request, dataset)
        if error is not None:
            return error
        service.lock_dataset(dataset)
        try:
            kwargs = {"config_overrides": overrides} if overrides else {}
            service.queue_task(PROCESS_DATASET_TASK, dataset.pk, **kwargs)
        except Exception:  # noqa: BLE001
            dataset.group.release_processing_lock()
            raise
        return Response(status=status.HTTP_200_OK)


class DatasetFindingsView(BiographicAPIView):
    def get(self, request: Request, business_area_slug: str, program_id: str, dataset_id: int) -> Response:
        dataset = self.get_dataset()
        if isinstance(dataset, Response):
            return dataset
        if dataset.state not in BiographicSet.FINDINGS_STATES:
            raise ConflictError(_FINDINGS_UNAVAILABLE)
        findings, error = service.filter_findings(dataset, request)
        if error is not None:
            return error
        return Response({"results": [service.finding_payload(finding) for finding in findings]})


class DatasetApproveView(BiographicAPIView):
    def post(self, request: Request, business_area_slug: str, program_id: str, dataset_id: int) -> Response:
        return service.transition(self.get_dataset(), BiographicSet.State.APPROVED)


class DatasetRejectView(BiographicAPIView):
    def post(self, request: Request, business_area_slug: str, program_id: str, dataset_id: int) -> Response:
        return service.transition(self.get_dataset(), BiographicSet.State.REJECTED)
