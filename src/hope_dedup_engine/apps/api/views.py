from http import HTTPMethod
from typing import Any, cast

from django.db import transaction
from django.db.models import QuerySet, Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from hope_dedup_engine.apps.api.auth import (
    CanUseApi,
    HDETokenAuthentication,
)
from django_filters.rest_framework import DjangoFilterBackend

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
)
from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig, get_default_group_settings
from hope_dedup_engine.apps.api.utils.process import delete_model_data


def get_active_deduplication_sets(request: Request) -> QuerySet[DeduplicationSet]:
    return cast(
        "QuerySet[DeduplicationSet]",
        DeduplicationSet.objects.filter(group__system=request.auth.system, group__deleted=False).exclude(
            state=DeduplicationSet.State.APPROVED,
        ),
    )


class DeduplicationSetViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = (IsAuthenticated, CanUseApi)
    serializer_class = DeduplicationSetSerializer
    lookup_field = "pk"

    def get_queryset(self) -> QuerySet["DeduplicationSet"]:
        return (
            get_active_deduplication_sets(self.request)
            .select_related("group")
            .annotate(findings_count=Count("finding"))
        )

    def get_serializer_class(self) -> type[Serializer]:
        if self.action == "create":
            return CreateDeduplicationSetSerializer
        return super().get_serializer_class()

    def perform_create(self, serializer: Serializer) -> None:
        group_data = serializer.validated_data["group"]
        group, created = DeduplicationSetGroup.objects.update_or_create(
            system=self.request.auth.system,
            reference_pk=group_data["reference_pk"],
            defaults={"name": group_data.get("name")},
        )
        if created:
            group.settings = get_default_group_settings()
            group.save(update_fields=["settings"])
        serializer.save(group=group, created_by=self.request.user)

    def perform_destroy(self, instance: DeduplicationSet) -> None:
        instance.updated_by = self.request.user
        instance.save(update_fields=["updated_by"])
        delete_model_data(instance)

    @extend_schema(
        request=EmptySerializer,
        responses=EmptySerializer,
        description="Run encoding and/or deduplication for the deduplication set",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def process(self, request: Request, pk: str | None = None) -> Response:
        deduplication_set = self.get_object()

        if deduplication_set.state not in DeduplicationSet.PROCESSABLE_STATES:
            return Response(
                {"detail": f"Cannot process set in '{deduplication_set.get_state_display()}' state."},
                status=status.HTTP_409_CONFLICT,
            )

        group = deduplication_set.group
        if not group.acquire_processing_lock():
            return Response(
                {"detail": "Another task is already running for this group."},
                status=status.HTTP_409_CONFLICT,
            )

        deduplication_set.set_state(DeduplicationSet.State.ENCODING_IN_PROGRESS)
        job = MainJob.objects.create(deduplication_set=deduplication_set)
        job.queue()
        return Response({"message": "started"})

    @extend_schema(
        request=EmptySerializer,
        responses=EmptySerializer,
        description="Reject the deduplication set findings",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def reject(self, request: Request, pk: str | None = None) -> Response:
        deduplication_set = self.get_object()

        if deduplication_set.state != DeduplicationSet.State.DEDUPLICATED:
            return Response(
                {"detail": f"Cannot reject set in '{deduplication_set.get_state_display()}' state."},
                status=status.HTTP_409_CONFLICT,
            )

        deduplication_set.set_state(DeduplicationSet.State.REJECTED)
        deduplication_set.updated_by = self.request.user
        deduplication_set.save(update_fields=["updated_by"])
        return Response({"message": "ok"})

    @extend_schema(description="List all deduplication sets available to the user")
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=CreateDeduplicationSetSerializer,
        description="Create new deduplication set",
    )
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().create(request, *args, **kwargs)

    @extend_schema(description="Retrieve specific deduplication set")
    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(description="Delete specific deduplication set")
    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().destroy(request, *args, **kwargs)


class BulkEncodingViewSet(
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = (IsAuthenticated, CanUseApi)
    serializer_class = CreateEncodingSerializer
    queryset = Encoding.objects.all()

    def _get_deduplication_set(self) -> DeduplicationSet:
        ds_pk = self.kwargs["deduplication_set_pk"]
        return get_object_or_404(get_active_deduplication_sets(self.request), pk=ds_pk)

    def get_serializer(self, *args: Any, **kwargs: Any) -> Serializer:
        return CreateEncodingSerializer(*args, **kwargs, many=True)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        deduplication_set = self._get_deduplication_set()

        allowed = (DeduplicationSet.State.EMPTY, DeduplicationSet.State.UPLOADING_IN_PROGRESS)
        if deduplication_set.state not in allowed:
            return Response(
                {"detail": f"Cannot upload images in '{deduplication_set.get_state_display()}' state."},
                status=status.HTTP_409_CONFLICT,
            )

        if isinstance(request.data, list):
            for item in request.data:
                item["deduplication_set"] = deduplication_set.pk
        else:
            request.data["deduplication_set"] = deduplication_set.pk

        response = super().create(request, *args, **kwargs)

        is_last = request.query_params.get("last", "").lower() in ("true", "1")
        if deduplication_set.state == DeduplicationSet.State.EMPTY:
            target_state = DeduplicationSet.State.READY if is_last else DeduplicationSet.State.UPLOADING_IN_PROGRESS
            deduplication_set.set_state(target_state)
        elif is_last:
            deduplication_set.set_state(DeduplicationSet.State.READY)

        deduplication_set.updated_by = request.user
        deduplication_set.save(update_fields=["updated_by"])
        return response

    @extend_schema(description="Delete all images from deduplication set")
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

    authentication_classes = (HDETokenAuthentication,)
    permission_classes = (IsAuthenticated, CanUseApi)
    lookup_field = "reference_pk"

    def _get_group(self, request: Request, reference_pk: str) -> DeduplicationSetGroup:
        return DeduplicationSetGroup.objects.get(
            reference_pk=reference_pk,
            system=request.auth.system,
            deleted=False,
        )

    @extend_schema(
        methods=["GET"],
        responses=GroupSettingsSerializer,
        description="Get quality threshold settings for a deduplication set group.",
    )
    @extend_schema(
        methods=["POST"],
        request=GroupSettingsSerializer,
        responses=GroupSettingsSerializer,
        description="Create or update quality threshold settings for a deduplication set group.",
    )
    @action(detail=True, methods=(HTTPMethod.GET, HTTPMethod.POST), url_path="config")
    def config(self, request: Request, reference_pk: str) -> Response:
        if request.method == "GET":
            return self._config_retrieve(request, reference_pk)
        return self._config_update(request, reference_pk)

    def _config_retrieve(self, request: Request, reference_pk: str) -> Response:
        group = DeduplicationSetGroup.objects.filter(reference_pk=reference_pk, system=request.auth.system).first()
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
            system=request.auth.system,
            defaults={"settings": get_default_group_settings()},
        )

        try:
            group.update_settings(serializer.validated_data)
        except GroupSettingsError as e:
            return Response(
                {"detail": "The provided group settings are invalid."},
                status=status.HTTP_409_CONFLICT,
            )

        api_fields = [f.name for f in DeduplicationSetConfig.setting_fields(api=True)]
        return Response({k: group.settings[k] for k in api_fields if k in group.settings})

    @extend_schema(
        request=EmptySerializer,
        responses=EmptySerializer,
        description="Approve the deduplicated set in this group (used by HOPE).",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def approve(self, request: Request, reference_pk: str) -> Response:
        group = self._get_group(request, reference_pk)
        deduplication_set = group.deduplicationset_set.filter(
            state=DeduplicationSet.State.DEDUPLICATED,
        ).first()

        if deduplication_set is None:
            return Response(
                {"detail": "No deduplicated set found in this group."},
                status=status.HTTP_404_NOT_FOUND,
            )

        deduplication_set.set_state(DeduplicationSet.State.APPROVED)
        deduplication_set.updated_by = request.user
        deduplication_set.save(update_fields=["updated_by"])
        return Response({"message": "ok"})


class GroupFindingsViewSet(
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Paginated, filterable findings for a deduplication set group (used by HOPE)."""

    authentication_classes = (HDETokenAuthentication,)
    permission_classes = (IsAuthenticated, CanUseApi)
    serializer_class = DuplicateSerializer
    queryset = Finding.objects.none()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = FindingFilter
    pagination_class = FindingResultsPagination

    def get_queryset(self) -> QuerySet[Finding]:
        return (
            Finding.objects.filter(
                deduplication_set__group__reference_pk=self.kwargs["reference_pk"],
                deduplication_set__group__system=self.request.auth.system,
                deduplication_set__group__deleted=False,
                deduplication_set__state=DeduplicationSet.State.DEDUPLICATED,
            )
            .select_related("first_encoding", "second_encoding")
            .order_by("-updated_at", "-id")
        )
