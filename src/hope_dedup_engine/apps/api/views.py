from http import HTTPMethod
from typing import Any, cast

from django.db import transaction
from django.db.models import QuerySet, Count
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from hope_api_auth.auth import GrantedPermission, LoggingTokenAuthentication

from hope_dedup_engine.apps.api.grant import Grant
from hope_dedup_engine.apps.api.filters import FindingFilter
from hope_dedup_engine.apps.api.models import (
    DeduplicationSet,
    Finding,
    Encoding,
)
from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSetGroup, GroupSettingsError
from hope_dedup_engine.apps.api.models.jobs import MainJob
from hope_dedup_engine.apps.api.pagination import FindingResultsPagination
from hope_dedup_engine.apps.api.serializers import (
    CreateDeduplicationSetSerializer,
    CreateEncodingSerializer,
    DeduplicationSetSerializer,
    DuplicateSerializer,
    EmptySerializer,
    GroupSettingsSerializer,
    GroupStatusSerializer,
)
from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig, get_default_group_settings
from hope_dedup_engine.apps.api.exceptions import ConflictError
from hope_dedup_engine.apps.api.utils.process import delete_model_data


def get_active_deduplication_sets() -> QuerySet[DeduplicationSet]:
    return cast(
        "QuerySet[DeduplicationSet]",
        DeduplicationSet.objects.filter(group__deleted=False).exclude(state=DeduplicationSet.State.APPROVED),
    )


class DeduplicationSetViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (LoggingTokenAuthentication,)
    permission_classes = (GrantedPermission,)
    permission = Grant.API_DEDUP
    serializer_class = DeduplicationSetSerializer
    lookup_field = "pk"

    def get_queryset(self) -> QuerySet["DeduplicationSet"]:
        return get_active_deduplication_sets().select_related("group").annotate(findings_count=Count("finding"))

    def get_serializer_class(self) -> type[Serializer]:
        if self.action == "create":
            return CreateDeduplicationSetSerializer
        return super().get_serializer_class()

    def perform_create(self, serializer: Serializer) -> None:
        group_data = serializer.validated_data["group"]
        group, created = DeduplicationSetGroup.objects.update_or_create(
            reference_pk=group_data["reference_pk"],
            defaults={"name": group_data.get("name")},
        )
        if created:
            group.settings = get_default_group_settings()
            group.save(update_fields=["settings"])
        elif group.deduplicationset_set.filter(state__in=DeduplicationSet.BLOCKING_STATES).exists():
            raise ConflictError("A deduplication set is already active in this group.")
        serializer.save(group=group, created_by=self.request.user)

    def perform_destroy(self, instance: DeduplicationSet) -> None:
        instance.updated_by = self.request.user
        instance.save(update_fields=["updated_by"])
        delete_model_data(instance)

    @extend_schema(
        request=EmptySerializer,
        responses=EmptySerializer,
        parameters=[
            OpenApiParameter(
                name="encode_only",
                type=bool,
                location=OpenApiParameter.QUERY,
                required=False,
                description="If true, only run encoding without deduplication.",
            ),
        ],
        description="Start encoding and deduplication for the deduplication set. "
        "Pass encode_only=true to run encoding without deduplication. "
        "Allowed in Ready, Encoded, Encoding failed, or Deduplication failed states. "
        "Returns 409 if the set is in a non-processable state or another task is already running for the group.",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def process(self, request: Request, pk: str | None = None) -> Response:
        deduplication_set = self.get_object()

        if deduplication_set.state not in DeduplicationSet.PROCESSABLE_STATES:
            raise ConflictError(f"Cannot process set in '{deduplication_set.get_state_display()}' state.")

        group = deduplication_set.group
        if not group.acquire_processing_lock():
            raise ConflictError("Another task is already running for this group.")

        encode_only = request.query_params.get("encode_only", "").lower() in ("true", "1")

        try:
            with transaction.atomic():
                deduplication_set.set_state(DeduplicationSet.State.ENCODING_IN_PROGRESS)
                job = MainJob.objects.create(deduplication_set=deduplication_set, encode_only=encode_only)
        except Exception:
            group.release_processing_lock()
            raise

        job.queue()
        return Response({"message": "started"})

    @extend_schema(
        request=EmptySerializer,
        responses=EmptySerializer,
        description="Reject the deduplication set findings and move the set back to a state "
        "where it can be reprocessed or deleted. "
        "Only allowed when the set is in 'Deduplicated' state.",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def reject(self, request: Request, pk: str | None = None) -> Response:
        deduplication_set = self.get_object()

        if deduplication_set.state != DeduplicationSet.State.DEDUPLICATED:
            raise ConflictError(f"Cannot reject set in '{deduplication_set.get_state_display()}' state.")

        deduplication_set.set_state(DeduplicationSet.State.REJECTED)
        deduplication_set.updated_by = self.request.user
        deduplication_set.save(update_fields=["updated_by"])
        return Response({"message": "ok"})

    @extend_schema(
        request=EmptySerializer,
        responses=EmptySerializer,
        description="Approve the deduplication set, marking it as final. "
        "Only allowed when the set is in 'Deduplicated' state.",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def approve(self, request: Request, pk: str | None = None) -> Response:
        deduplication_set = self.get_object()

        if deduplication_set.state != DeduplicationSet.State.DEDUPLICATED:
            raise ConflictError(f"Cannot approve set in '{deduplication_set.get_state_display()}' state.")

        deduplication_set.set_state(DeduplicationSet.State.APPROVED)
        deduplication_set.updated_by = request.user
        deduplication_set.save(update_fields=["updated_by"])
        return Response({"message": "ok"})

    @extend_schema(description="List all non-approved deduplication sets.")
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=CreateDeduplicationSetSerializer,
        description="Create a new deduplication set within a group. "
        "The group is identified by reference_pk and created automatically if it does not exist. "
        "Returns 409 if an active deduplication set already exists in the group.",
    )
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().create(request, *args, **kwargs)

    @extend_schema(
        description="Retrieve a specific deduplication set by ID, including its current state and findings count.",
    )
    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        description="Delete a specific deduplication set and all its associated images, encodings, and findings.",
    )
    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        request=EmptySerializer,
        responses=EmptySerializer,
        description="Mark the deduplication set as ready for processing. "
        "Call this after all image upload batches have completed. "
        "Only allowed when the set is in 'Uploading in progress' state.",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def ready(self, request: Request, pk: str | None = None) -> Response:
        deduplication_set = self.get_object()
        if deduplication_set.state != DeduplicationSet.State.UPLOADING_IN_PROGRESS:
            raise ConflictError(f"Cannot mark as ready in '{deduplication_set.get_state_display()}' state.")
        deduplication_set.set_state(DeduplicationSet.State.READY)
        return Response(status=status.HTTP_200_OK)


class BulkEncodingViewSet(
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (LoggingTokenAuthentication,)
    permission_classes = (GrantedPermission,)
    permission = Grant.API_DEDUP
    serializer_class = CreateEncodingSerializer
    queryset = Encoding.objects.all()

    def _get_deduplication_set(self) -> DeduplicationSet:
        ds_pk = self.kwargs["deduplication_set_pk"]
        return get_object_or_404(get_active_deduplication_sets(), pk=ds_pk)

    def get_serializer(self, *args: Any, **kwargs: Any) -> Serializer:
        return CreateEncodingSerializer(*args, **kwargs, many=True)

    @extend_schema(
        description="Register a batch of images in the deduplication set. "
        "Can be called multiple times in parallel. "
        "After all batches are uploaded, call the 'ready' endpoint to finalize.",
    )
    @transaction.atomic
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        deduplication_set = self._get_deduplication_set()

        allowed = (DeduplicationSet.State.EMPTY, DeduplicationSet.State.UPLOADING_IN_PROGRESS)
        if deduplication_set.state not in allowed:
            raise ConflictError(f"Cannot upload images in '{deduplication_set.get_state_display()}' state.")

        for item in request.data:
            item["deduplication_set"] = deduplication_set.pk

        response = super().create(request, *args, **kwargs)

        if deduplication_set.state == DeduplicationSet.State.EMPTY:
            deduplication_set.set_state(DeduplicationSet.State.UPLOADING_IN_PROGRESS)

        deduplication_set.updated_by = request.user
        deduplication_set.save(update_fields=["updated_by"])
        return response

    @extend_schema(
        description="Delete all registered images from the deduplication set and reset its state to Empty.",
    )
    @action(detail=False, methods=(HTTPMethod.DELETE,))
    def clear(self, request: Request, deduplication_set_pk: str) -> Response:
        deduplication_set = self._get_deduplication_set()
        Encoding.objects.filter(deduplication_set=deduplication_set).delete()
        deduplication_set.state = DeduplicationSet.State.EMPTY
        deduplication_set.error = None
        deduplication_set.updated_by = request.user
        deduplication_set.save(update_fields=["state", "error", "updated_by"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeduplicationSetGroupView(viewsets.ViewSet):
    """Group-level endpoints used by HOPE (by group reference_pk) and for config management."""

    authentication_classes = (LoggingTokenAuthentication,)
    permission_classes = (GrantedPermission,)
    permission = Grant.API_DEDUP
    lookup_field = "reference_pk"

    @extend_schema(
        methods=["GET"],
        responses=GroupSettingsSerializer,
        description="Get quality threshold settings for a deduplication set group. "
        "Returns default values if the group does not exist or has no custom settings.",
    )
    @extend_schema(
        methods=["POST"],
        request=GroupSettingsSerializer,
        responses=GroupSettingsSerializer,
        description="Create or update quality threshold settings for a deduplication set group. "
        "Creates the group if it does not exist. "
        "Returns 409 if the group has an approved set or a processing job is running. "
        "If a deduplicated or encoded set exists, its embeddings and findings are cleared "
        "so new settings take effect on the next processing.",
    )
    @action(detail=True, methods=(HTTPMethod.GET, HTTPMethod.POST), url_path="config")
    def config(self, request: Request, reference_pk: str) -> Response:
        if request.method == "GET":
            return self._config_retrieve(reference_pk)
        return self._config_update(request, reference_pk)

    def _config_retrieve(self, reference_pk: str) -> Response:
        group = DeduplicationSetGroup.objects.filter(reference_pk=reference_pk).first()
        defaults = get_default_group_settings()
        if group and group.settings:
            defaults.update(group.settings)
        api_fields = [f.name for f in DeduplicationSetConfig.setting_fields(api=True)]
        return Response({k: defaults[k] for k in api_fields if k in defaults})

    @transaction.atomic
    def _config_update(self, request: Request, reference_pk: str) -> Response:
        serializer = GroupSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        group, _ = DeduplicationSetGroup.objects.get_or_create(
            reference_pk=reference_pk,
            defaults={"settings": get_default_group_settings()},
        )

        try:
            group.update_settings(serializer.validated_data)
        except GroupSettingsError as e:
            raise ConflictError(str(e))

        api_fields = [f.name for f in DeduplicationSetConfig.setting_fields(api=True)]
        return Response({k: group.settings[k] for k in api_fields if k in group.settings})

    @extend_schema(
        responses=GroupStatusSerializer,
        description="Check whether a new deduplication set can be created in this group. "
        "Returns can_create=false if a set that is currently being uploaded, "
        "processed, or awaiting approval already exists in the group.",
    )
    @action(detail=True, methods=(HTTPMethod.GET,), url_path="status")
    def status(self, request: Request, reference_pk: str) -> Response:
        has_active = DeduplicationSet.objects.filter(
            group__reference_pk=reference_pk,
            group__deleted=False,
            state__in=DeduplicationSet.BLOCKING_STATES,
        ).exists()
        return Response(GroupStatusSerializer({"can_create": not has_active}).data)


class FindingsViewSet(
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Paginated, filterable findings for a deduplication set (used by HOPE)."""

    authentication_classes = (LoggingTokenAuthentication,)
    permission_classes = (GrantedPermission,)
    permission = Grant.API_READ_ONLY
    serializer_class = DuplicateSerializer
    queryset = Finding.objects.none()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = FindingFilter
    pagination_class = FindingResultsPagination

    def get_queryset(self) -> QuerySet[Finding]:
        return (
            Finding.objects.filter(
                deduplication_set__pk=self.kwargs["deduplication_set_pk"],
                deduplication_set__group__deleted=False,
                deduplication_set__state__in=[DeduplicationSet.State.DEDUPLICATED, DeduplicationSet.State.APPROVED],
            )
            .select_related("first_encoding", "second_encoding")
            .order_by("-updated_at", "-id")
        )
