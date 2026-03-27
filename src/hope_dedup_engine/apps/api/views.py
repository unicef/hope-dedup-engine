from dataclasses import dataclass
from http import HTTPMethod
from typing import Any, cast

from django.db.models import QuerySet, Model, Count
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework_nested import viewsets as nested_viewsets

from hope_dedup_engine.apps.api.auth import (
    CanUseApi,
    HDETokenAuthentication,
    HasAccessToDeduplicationSet,
)
from hope_dedup_engine.apps.api.const import (
    DEDUPLICATION_SET_GROUP_FILTER,
    DEDUPLICATION_SET_GROUP_PARAM,
)
from hope_dedup_engine.apps.api.filters import FindingFilter
from hope_dedup_engine.apps.api.models import (
    DeduplicationSet,
    Finding,
    IgnoredFilenamePair,
    IgnoredReferencePkPair,
    Encoding,
)
from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSetGroup
from hope_dedup_engine.apps.api.models.jobs import MainJob
from hope_dedup_engine.apps.api.pagination import FindingResultsPagination
from hope_dedup_engine.apps.api.serializers import (
    CreateDeduplicationSetSerializer,
    CreateIgnoredFilenamePairSerializer,
    CreateIgnoredReferencePkPairSerializer,
    CreateEncodingSerializer,
    DeduplicationSetSerializer,
    DuplicateSerializer,
    EmptySerializer,
    IgnoredFilenamePairSerializer,
    IgnoredReferencePkPairSerializer,
    EncodingSerializer,
    ApproveOrRejectSerializer,
    GroupSettingsSerializer,
)
from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig, get_default_group_settings
from hope_dedup_engine.apps.api.utils.process import delete_model_data


def get_active_deduplication_sets(request: Request) -> QuerySet[DeduplicationSet]:
    return cast(
        "QuerySet[DeduplicationSet]",
        DeduplicationSet.objects.filter(group__system=request.auth.system, group__deleted=False).exclude(
            state__in=[DeduplicationSet.State.INACTIVE, DeduplicationSet.State.REJECTED]
        ),
    )


def get_deduplication_set(request: Request, group_reference_pk: str) -> DeduplicationSet:
    return get_active_deduplication_sets(request).get(group__reference_pk=group_reference_pk)


class DeduplicationSetViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = (
        IsAuthenticated,
        CanUseApi,
        HasAccessToDeduplicationSet,
    )
    serializer_class = DeduplicationSetSerializer
    lookup_field = "group__reference_pk"

    def get_queryset(self) -> QuerySet["DeduplicationSet"]:
        return (
            get_active_deduplication_sets(self.request)
            .select_related("group")
            .annotate(duplicates_found=Count("finding"))
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
        instance.group.deleted = True
        instance.group.save()
        instance.save()
        delete_model_data(instance)

    @extend_schema(
        request=EmptySerializer,
        responses=EmptySerializer,
        description="Run duplicate search process for the deduplication set",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def process(self, request: Request, group__reference_pk: str | None = None) -> Response:
        deduplication_set = self.get_object()
        job = MainJob.objects.create(deduplication_set=deduplication_set)
        job.queue()
        return Response({"message": "started"})

    @extend_schema(
        request=ApproveOrRejectSerializer,
        responses=EmptySerializer,
        description="Approve deduplication set or individual records",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def approve_or_reject(self, request: Request, group__reference_pk: str | None = None) -> Response:
        deduplication_set = self.get_object()
        serializer = ApproveOrRejectSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            action_ = serializer.validated_data["action"]

            if action_ == "approve":
                deduplication_set.state = DeduplicationSet.State.INACTIVE
            else:
                deduplication_set.state = DeduplicationSet.State.REJECTED

            deduplication_set.updated_by = self.request.user
            deduplication_set.save(
                update_fields=["state", "updated_by"],
            )

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


class UseGroupReferencePkMixin:
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        if group_reference_pk := kwargs.get("deduplication_set_group__reference_pk"):
            deduplication_set = get_deduplication_set(request, group_reference_pk)
            if isinstance(request.data, list):
                for i in request.data:
                    i["deduplication_set"] = deduplication_set.pk
            else:
                request.data["deduplication_set"] = deduplication_set.pk

        return super().create(request, *args, **kwargs)


class EncodingViewSet(
    UseGroupReferencePkMixin,
    nested_viewsets.NestedViewSetMixin[Encoding],
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = (
        IsAuthenticated,
        CanUseApi,
        HasAccessToDeduplicationSet,
    )
    serializer_class = EncodingSerializer
    queryset = Encoding.objects.all()
    parent_lookup_kwargs = {
        DEDUPLICATION_SET_GROUP_PARAM: DEDUPLICATION_SET_GROUP_FILTER,
    }

    def get_serializer_class(self) -> type[Serializer]:
        if self.action == "create":
            return CreateEncodingSerializer
        return super().get_serializer_class()

    def perform_create(self, serializer: Serializer) -> None:
        super().perform_create(serializer)
        deduplication_set = serializer.instance.deduplication_set
        deduplication_set.state = DeduplicationSet.State.MODIFIED
        deduplication_set.updated_by = self.request.user
        deduplication_set.save()

    def perform_destroy(self, instance: Encoding) -> None:
        deduplication_set = instance.deduplication_set
        super().perform_destroy(instance)
        deduplication_set.state = DeduplicationSet.State.MODIFIED
        deduplication_set.updated_by = self.request.user
        deduplication_set.save()

    @extend_schema(description="List all images for the deduplication set")
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    @extend_schema(request=CreateEncodingSerializer, description="Add image to the deduplication set")
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().create(request, *args, **kwargs)

    @extend_schema(description="Delete image from the deduplication set")
    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().destroy(request, *args, **kwargs)


@dataclass
class ListDataWrapper:
    data: list[dict[str, Any]]

    def __setitem__(self, key: str, value: Any) -> None:
        for item in self.data:
            item[key] = value


class WrapRequestDataMixin:
    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)
        request._full_data = ListDataWrapper(request.data)


class UnwrapRequestDataMixin:
    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)
        request._full_data = request._full_data.data


# drf-nested-routers doesn't work correctly when request data is a list, so we use WrapRequestDataMixin,
# UnwrapRequestDataMixin, and ListDataWrapper to make it work with list of objects
class BulkEncodingViewSet(
    UseGroupReferencePkMixin,
    UnwrapRequestDataMixin,
    nested_viewsets.NestedViewSetMixin[Encoding],
    WrapRequestDataMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = (
        IsAuthenticated,
        CanUseApi,
        HasAccessToDeduplicationSet,
    )
    serializer_class = EncodingSerializer
    queryset = Encoding.objects.all()
    parent_lookup_kwargs = {
        DEDUPLICATION_SET_GROUP_PARAM: DEDUPLICATION_SET_GROUP_FILTER,
    }

    def get_serializer(self, *args: Any, **kwargs: Any) -> Serializer:
        if self.action == "create":
            return CreateEncodingSerializer(*args, **kwargs, many=True)
        return super().get_serializer(*args, **kwargs, many=True)

    def perform_create(self, serializer: Serializer) -> None:
        super().perform_create(serializer)
        if deduplication_set := (serializer.instance[0].deduplication_set if serializer.instance else None):
            deduplication_set.updated_by = self.request.user
            deduplication_set.save()

    @extend_schema(description="Delete all images from deduplication set")
    @action(detail=False, methods=(HTTPMethod.DELETE,))
    def clear(self, request: Request, deduplication_set_group__reference_pk: str) -> Response:
        deduplication_set = get_deduplication_set(request, deduplication_set_group__reference_pk)
        Encoding.objects.filter(deduplication_set=deduplication_set).delete()
        deduplication_set.updated_by = request.user
        deduplication_set.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=CreateEncodingSerializer(many=True),
        description="Add multiple images to the deduplication set",
    )
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().create(request, *args, **kwargs)


class DuplicateViewSet(
    UseGroupReferencePkMixin,
    nested_viewsets.NestedViewSetMixin[Finding],
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = (
        IsAuthenticated,
        CanUseApi,
        HasAccessToDeduplicationSet,
    )
    serializer_class = DuplicateSerializer
    queryset = Finding.objects.select_related("first_encoding", "second_encoding").order_by("-updated_at", "-id")
    filterset_class = FindingFilter
    parent_lookup_kwargs = {
        DEDUPLICATION_SET_GROUP_PARAM: DEDUPLICATION_SET_GROUP_FILTER,
    }
    pagination_class = FindingResultsPagination

    @extend_schema(
        description="List all duplicates found in the deduplication set",
    )
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)


class IgnoredPairViewSet[T: Model](
    UseGroupReferencePkMixin,
    nested_viewsets.NestedViewSetMixin[T],
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = (
        IsAuthenticated,
        CanUseApi,
        HasAccessToDeduplicationSet,
    )
    parent_lookup_kwargs = {
        DEDUPLICATION_SET_GROUP_PARAM: DEDUPLICATION_SET_GROUP_FILTER,
    }

    def perform_create(self, serializer: Serializer) -> None:
        super().perform_create(serializer)
        deduplication_set = serializer.instance.deduplication_set
        deduplication_set.state = DeduplicationSet.State.MODIFIED
        deduplication_set.updated_by = self.request.user
        deduplication_set.save()


class IgnoredFilenamePairViewSet(IgnoredPairViewSet[IgnoredFilenamePair]):
    serializer_class = IgnoredFilenamePairSerializer
    queryset = IgnoredFilenamePair.objects.all()

    @extend_schema(description="List all ignored filename pairs for the deduplication set")
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=CreateIgnoredFilenamePairSerializer,
        description="Add ignored filename pair for the deduplication set",
    )
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().create(request, *args, **kwargs)


class IgnoredReferencePkPairViewSet(IgnoredPairViewSet[IgnoredReferencePkPair]):
    serializer_class = IgnoredReferencePkPairSerializer
    queryset = IgnoredReferencePkPair.objects.all()

    @extend_schema(description="List all ignored reference pk pairs for the deduplication set")
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=CreateIgnoredReferencePkPairSerializer,
        description="Add ignored reference pk pair for the deduplication set",
    )
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().create(request, *args, **kwargs)


class DeduplicationSetGroupConfigView(viewsets.ViewSet):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = (IsAuthenticated, CanUseApi)
    serializer_class = GroupSettingsSerializer

    def _api_field_names(self) -> list[str]:
        return [f.name for f in DeduplicationSetConfig.setting_fields(api=True)]

    def _get_settings_for_response(self, group: DeduplicationSetGroup | None) -> dict[str, Any]:
        defaults = get_default_group_settings()
        if group and group.settings:
            defaults.update(group.settings)
        return {k: defaults[k] for k in self._api_field_names() if k in defaults}

    @extend_schema(
        responses=GroupSettingsSerializer,
        description="Get quality threshold settings for a deduplication set group.",
    )
    def retrieve(self, request: Request, reference_pk: str) -> Response:
        group = DeduplicationSetGroup.objects.filter(reference_pk=reference_pk, system=request.auth.system).first()
        return Response(self._get_settings_for_response(group))

    @extend_schema(
        request=GroupSettingsSerializer,
        responses=GroupSettingsSerializer,
        description="Create or update quality threshold settings for a deduplication set group.",
    )
    def update(self, request: Request, reference_pk: str) -> Response:
        serializer = GroupSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        group, created = DeduplicationSetGroup.objects.get_or_create(
            reference_pk=reference_pk,
            system=request.auth.system,
            defaults={"settings": get_default_group_settings()},
        )

        if not created and group.has_inactive_deduplication_sets():
            return Response(
                {"detail": "Cannot change settings while inactive deduplication sets exist."},
                status=status.HTTP_409_CONFLICT,
            )

        if not group.settings:
            group.settings = get_default_group_settings()

        for key, value in serializer.validated_data.items():
            group.settings[key] = value

        group.save(update_fields=["settings"])

        if not created and group.has_calculated_embeddings():
            for ds in group.deduplicationset_set.all():
                ds.encoding_set.update(embedding=None, embedding_status_code=None)
                ds.finding_set.all().delete()
                MainJob.objects.create(deduplication_set=ds, encode_only=True).queue()

        return Response(self._get_settings_for_response(group))
