from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http import HTTPMethod
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Count, OuterRef, QuerySet, Subquery
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from hope_api_auth.views import TokenRequiredView
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.validators import UniqueValidator

from hope_dedup_engine.apps.api.exceptions import ConflictError
from hope_dedup_engine.apps.api.grant import Grant
from hope_dedup_engine.apps.api.pagination import FindingResultsPagination
from hope_dedup_engine.apps.api.serializers import EmptySerializer
from hope_dedup_engine.apps.biographic.config import get_default_group_settings
from hope_dedup_engine.apps.biographic.exceptions import GroupDeleteError, LifecycleConflictError
from hope_dedup_engine.apps.biographic.filters import BiographicFindingFilter
from hope_dedup_engine.apps.biographic.models import BiographicFinding, BiographicGroup, BiographicSet
from hope_dedup_engine.apps.biographic.serializers import (
    MAX_RECORDS_PER_BATCH,
    BiographicFindingSerializer,
    BiographicSetCreateSerializer,
    BiographicSetSerializer,
    ProcessOverridesSerializer,
    RecordsBatchResultSerializer,
    RecordsBatchSerializer,
)
from hope_dedup_engine.apps.biographic.services import lifecycle

# drf-spectacular tags by the first path segment, which is "api" for every route here.
SCHEMA_TAGS = ["biographic"]

# Either case, on every route: a UUID names the same set however it is written.
UUID_REGEX = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"


def duplicates_in_scope(scope: BiographicFinding.Scope) -> Coalesce:
    """Count the set's records with at least one finding in `scope`, as HOPE counts per individual.

    A correlated subquery rather than a join: joined onto `records_count` it
    would multiply the rows, and a set can have hundreds of thousands of findings.
    """
    findings = (
        BiographicFinding.objects.filter(dataset=OuterRef("pk"), scope=scope)
        .order_by()
        .values("dataset")
        .annotate(n=Count("record", distinct=True))
        .values("n")
    )
    return Coalesce(Subquery(findings[:1]), 0)


@contextmanager
def conflicts_as_409() -> Iterator[None]:
    try:
        yield
    except LifecycleConflictError as error:
        raise ConflictError(str(error)) from error


class BiographicProgramMixin:
    """Resolves the business area and program from the URL.

    Both are lowercased: they become part of an Elasticsearch index name, which
    must be lowercase, and `AFG` and `afg` should not be two programs.
    """

    kwargs: dict[str, Any]

    def program_key(self) -> tuple[str, str]:
        return self.kwargs["business_area_slug"].lower(), self.kwargs["program_code"].lower()

    def program_sets(self) -> QuerySet[BiographicSet]:
        business_area, program_code = self.program_key()
        return BiographicSet.objects.filter(
            group__business_area=business_area,
            group__program_code=program_code,
            group__deleted=False,
        )


@extend_schema(tags=SCHEMA_TAGS)
class BiographicGroupView(BiographicProgramMixin, TokenRequiredView):
    """The program itself: soft delete."""

    permission = Grant.API_BIOGRAPHIC

    @extend_schema(
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_409_CONFLICT: OpenApiResponse(description=GroupDeleteError.message),
        },
        description="Soft-delete biographic deduplication for this program. Its sets are hidden from the API, "
        "and the program can be registered again by creating a new set. "
        "Returns 204 when the program does not exist or is already deleted, "
        "and 409 while a task is running for it.",
    )
    def delete(self, request: Request, **kwargs: Any) -> Response:
        business_area, program_code = self.program_key()
        group = BiographicGroup.objects.filter(
            business_area=business_area, program_code=program_code, deleted=False
        ).first()
        if group is not None:
            with conflicts_as_409():
                group.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=SCHEMA_TAGS)
class BiographicDatasetViewSet(
    BiographicProgramMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
    TokenRequiredView,
):
    permission = Grant.API_BIOGRAPHIC
    serializer_class = BiographicSetSerializer
    lookup_url_kwarg = "dataset_id"
    lookup_value_regex = UUID_REGEX

    def get_queryset(self) -> QuerySet[BiographicSet]:
        return (
            self.program_sets()
            .select_related("group")
            .annotate(
                records_count=Count("records"),
                batch_duplicates=duplicates_in_scope(BiographicFinding.Scope.BATCH),
                population_duplicates=duplicates_in_scope(BiographicFinding.Scope.POPULATION),
            )
        )

    def _respond(self, dataset: BiographicSet, status_code: int = status.HTTP_200_OK) -> Response:
        return Response(self.get_serializer(self.get_queryset().get(pk=dataset.pk)).data, status=status_code)

    def _apply(self, step: Callable[[BiographicSet], None]) -> Response:
        dataset = self.get_object()
        with conflicts_as_409():
            step(dataset)
        return self._respond(dataset)

    @extend_schema(
        request=BiographicSetCreateSerializer,
        responses={status.HTTP_201_CREATED: BiographicSetSerializer},
        description="Create an empty set for this business area and program. "
        "The program is registered on first use, or again after it was deleted. "
        "Creation is always allowed, even while another set is being processed; "
        "add people with the records endpoint. "
        "An optional id (UUID) names the set; one is generated when omitted, and an id "
        "already in use is rejected. "
        "An optional notification_url is pinged with a GET on every state change a run makes.",
    )
    @transaction.atomic
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = BiographicSetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        business_area, program_code = self.program_key()
        # The group's row stays locked until the response is built, so a concurrent
        # delete waits instead of hiding the set this request is about to return.
        group, _ = BiographicGroup.objects.select_for_update().get_or_create(
            business_area=business_area,
            program_code=program_code,
            deleted=False,
            defaults={"settings": get_default_group_settings()},
        )
        try:
            with transaction.atomic():
                dataset = BiographicSet.objects.create(group=group, **serializer.validated_data)
        except IntegrityError:
            # Another request took the same id between validation and insert.
            if "id" not in serializer.validated_data:
                raise
            raise ValidationError({"id": [UniqueValidator.message]}) from None
        return self._respond(dataset, status.HTTP_201_CREATED)

    @extend_schema(description="Current state of the set. Poll this after starting processing.")
    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        request=RecordsBatchSerializer,
        responses={status.HTTP_201_CREATED: RecordsBatchResultSerializer},
        description="Add a batch of people to a pending set. Call as many times as needed, "
        f"up to {MAX_RECORDS_PER_BATCH} records per call. "
        "A reference_pk already in the set is replaced, so a batch can be safely re-sent.",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def records(self, request: Request, **kwargs: Any) -> Response:
        dataset = self.get_object()
        serializer = RecordsBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with conflicts_as_409():
            received = lifecycle.add_records(dataset, serializer.validated_data["records"])
        result = {"received": received, "records_count": dataset.records.count()}
        return Response(RecordsBatchResultSerializer(result).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=ProcessOverridesSerializer,
        responses=BiographicSetSerializer,
        description="Index and deduplicate the set against itself and the program's approved population. "
        "The body may override any of the program's settings for this run. "
        "Returns 409 if the set is not pending or failed, has no records, or another set "
        "in the program is being processed or awaiting approval.",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def process(self, request: Request, **kwargs: Any) -> Response:
        overrides = ProcessOverridesSerializer(data=request.data)
        overrides.is_valid(raise_exception=True)

        def start(dataset: BiographicSet) -> None:
            lifecycle.start_processing(dataset, overrides.validated_data)

        return self._apply(start)

    @extend_schema(
        request=EmptySerializer,
        responses=BiographicSetSerializer,
        description="Abandon a pending or failed set. Its people never take part in deduplication.",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def cancel(self, request: Request, **kwargs: Any) -> Response:
        return self._apply(lifecycle.cancel)

    @extend_schema(
        request=EmptySerializer,
        responses=BiographicSetSerializer,
        description="Accept the findings. The set's people join the program's population, "
        "and later sets are deduplicated against them. Only allowed when deduplicated.",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def approve(self, request: Request, **kwargs: Any) -> Response:
        return self._apply(lambda dataset: lifecycle.decide(dataset, BiographicSet.State.APPROVED))

    @extend_schema(
        request=EmptySerializer,
        responses=BiographicSetSerializer,
        description="Discard the set. Its people never take part in deduplication again. "
        "Only allowed when deduplicated.",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def reject(self, request: Request, **kwargs: Any) -> Response:
        return self._apply(lambda dataset: lifecycle.decide(dataset, BiographicSet.State.REJECTED))


@extend_schema(tags=SCHEMA_TAGS)
class BiographicFindingsViewSet(
    BiographicProgramMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
    TokenRequiredView,
):
    """Paginated, filterable duplicate findings for one set.

    Findings are directional: when two people in the set match, the match is listed
    once from each side, as HOPE reports it per individual.
    """

    permission = Grant.API_BIOGRAPHIC
    serializer_class = BiographicFindingSerializer
    queryset = BiographicFinding.objects.none()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = BiographicFindingFilter
    pagination_class = FindingResultsPagination

    def get_queryset(self) -> QuerySet[BiographicFinding]:
        if getattr(self, "swagger_fake_view", False):
            return BiographicFinding.objects.none()
        dataset = get_object_or_404(self.program_sets(), pk=self.kwargs["dataset_id"])
        if dataset.state not in BiographicSet.FINDINGS_STATES:
            raise ConflictError(f"Findings are not available for set in '{dataset.get_state_display()}' state.")
        return BiographicFinding.objects.filter(dataset=dataset).select_related("record").order_by("-score", "-id")

    @extend_schema(
        parameters=[OpenApiParameter("dataset_id", OpenApiTypes.UUID, OpenApiParameter.PATH)],
        description="Duplicate findings for a deduplicated or approved set, best match first.",
    )
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)
