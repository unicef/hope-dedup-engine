from http import HTTPMethod
from typing import Any
from uuid import UUID

from django.db.models import QuerySet, Model
from django.http import HttpRequest
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework_nested import viewsets as nested_viewsets

from hope_dedup_engine.apps.api.models.jobs import DedupJob
from hope_dedup_engine.apps.api.auth import (
    CanUseApi,
    HDETokenAuthentication,
    HasAccessToDeduplicationSet,
)
from hope_dedup_engine.apps.api.const import (
    DEDUPLICATION_SET_FILTER,
    DEDUPLICATION_SET_PARAM,
)
from hope_dedup_engine.apps.api.models import (
    DeduplicationSet,
    Finding,
    IgnoredFilenamePair,
    IgnoredReferencePkPair,
    Image,
)
from hope_dedup_engine.apps.api.pagination import FindingResultsPagination
from hope_dedup_engine.apps.api.serializers import (
    CreateDeduplicationSetSerializer,
    CreateIgnoredFilenamePairSerializer,
    CreateIgnoredReferencePkPairSerializer,
    CreateImageSerializer,
    DeduplicationSetSerializer,
    DuplicateSerializer,
    EmptySerializer,
    IgnoredFilenamePairSerializer,
    IgnoredReferencePkPairSerializer,
    ImageSerializer,
)
from hope_dedup_engine.apps.api.utils.process import delete_model_data
from hope_dedup_engine.apps.api.filters import FindingFilter


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
    queryset = DeduplicationSet.objects.all()

    def get_queryset(self) -> QuerySet:
        return DeduplicationSet.objects.filter(system=self.request.auth.system, deleted=False)

    def perform_create(self, serializer: Serializer) -> None:
        serializer.save(
            created_by=self.request.user,
            system=self.request.auth.system,
        )

    def perform_destroy(self, instance: DeduplicationSet) -> None:
        instance.updated_by = self.request.user
        instance.deleted = True
        instance.save()
        delete_model_data(instance)

    @extend_schema(
        request=EmptySerializer,
        responses=EmptySerializer,
        description="Run duplicate search process for the deduplication set",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def process(self, request: Request, pk: UUID | None = None) -> Response:
        deduplication_set = self.get_object()
        job = DedupJob.objects.create(deduplication_set=deduplication_set)
        job.queue()
        return Response({"message": "started"})

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


class ImageViewSet(
    nested_viewsets.NestedViewSetMixin[Image],
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
    serializer_class = ImageSerializer
    queryset = Image.objects.all()
    parent_lookup_kwargs = {
        DEDUPLICATION_SET_PARAM: DEDUPLICATION_SET_FILTER,
    }

    def get_serializer_class(self) -> type[Serializer]:
        if self.action == "create":
            return CreateImageSerializer
        return super().get_serializer_class()

    def perform_create(self, serializer: Serializer) -> None:
        super().perform_create(serializer)
        deduplication_set = serializer.instance.deduplication_set
        deduplication_set.state = DeduplicationSet.State.MODIFIED
        deduplication_set.updated_by = self.request.user
        deduplication_set.save()

    def perform_destroy(self, instance: Image) -> None:
        deduplication_set = instance.deduplication_set
        super().perform_destroy(instance)
        deduplication_set.state = DeduplicationSet.State.MODIFIED
        deduplication_set.updated_by = self.request.user
        deduplication_set.save()

    @extend_schema(description="List all images for the deduplication set")
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    @extend_schema(request=CreateImageSerializer, description="Add image to the deduplication set")
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().create(request, *args, **kwargs)

    @extend_schema(description="Delete image from the deduplication set")
    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().destroy(request, *args, **kwargs)


class BulkImageViewSet(
    nested_viewsets.NestedViewSetMixin[Image],
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = (
        IsAuthenticated,
        CanUseApi,
        HasAccessToDeduplicationSet,
    )
    serializer_class = ImageSerializer
    queryset = Image.objects.all()
    parent_lookup_kwargs = {
        DEDUPLICATION_SET_PARAM: DEDUPLICATION_SET_FILTER,
    }

    def _inject_parent_lookup_kwargs(self, request_data: Any, view_kwargs: dict) -> None:
        """Inject parent lookup kwargs into request data, handling list-based data for bulk operations."""
        if getattr(self, "swagger_fake_view", False):
            return

        for url_kwarg, fk_filter in self._get_parent_lookup_kwargs().items():
            parent_arg = fk_filter.partition("__")[0]
            parent_pk = view_kwargs[url_kwarg]

            if isinstance(request_data, list):
                for item in request_data:
                    if isinstance(item, dict):
                        item[parent_arg] = parent_pk
            elif isinstance(request_data, dict):
                request_data[parent_arg] = parent_pk

    def initialize_request(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Request:
        """Override to bypass faulty drf-nested-routers logic and inject parent kwargs correctly."""
        drf_request: Request = super(nested_viewsets.NestedViewSetMixin, self).initialize_request(
            request, *args, **kwargs
        )
        self._inject_parent_lookup_kwargs(drf_request.data, kwargs)
        return drf_request

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        """Override to bypass faulty drf-nested-routers logic and inject parent kwargs correctly."""
        super(nested_viewsets.NestedViewSetMixin, self).initial(request, *args, **kwargs)
        self._inject_parent_lookup_kwargs(request.data, kwargs)

    def get_serializer(self, *args: Any, **kwargs: Any) -> Serializer:
        if self.action == "create":
            kwargs.setdefault("many", True)
            return CreateImageSerializer(*args, **kwargs)
        return super().get_serializer(*args, **kwargs)

    def perform_create(self, serializer: Serializer) -> None:
        super().perform_create(serializer)
        if serializer.instance:
            deduplication_set = serializer.instance[0].deduplication_set
            deduplication_set.updated_by = self.request.user
            deduplication_set.save()

    @extend_schema(description="Delete all images from deduplication set")
    @action(detail=False, methods=(HTTPMethod.DELETE,))
    def clear(self, request: Request, deduplication_set_pk: str) -> Response:
        deduplication_set = DeduplicationSet.objects.get(pk=deduplication_set_pk)
        Image.objects.filter(deduplication_set=deduplication_set).delete()
        deduplication_set.updated_by = request.user
        deduplication_set.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=CreateImageSerializer(many=True),
        description="Add multiple images to the deduplication set",
    )
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().create(request, *args, **kwargs)


class DuplicateViewSet(
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
    queryset = Finding.objects.all().order_by("-updated_at", "-id")
    filterset_class = FindingFilter
    parent_lookup_kwargs = {
        DEDUPLICATION_SET_PARAM: DEDUPLICATION_SET_FILTER,
    }
    pagination_class = FindingResultsPagination

    @extend_schema(
        description="List all duplicates found in the deduplication set",
    )
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)


class IgnoredPairViewSet[T: Model](
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
        DEDUPLICATION_SET_PARAM: DEDUPLICATION_SET_FILTER,
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
