from dataclasses import dataclass
from http import HTTPMethod
from typing import Any
from uuid import UUID

from django.db.models import QuerySet

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework_nested import viewsets as nested_viewsets

from hope_dedup_engine.apps.public_api.auth import (
    AssignedToExternalSystem,
    HDETokenAuthentication,
    UserAndDeduplicationSetAreOfTheSameSystem,
)
from hope_dedup_engine.apps.public_api.const import DEDUPLICATION_SET_FILTER, DEDUPLICATION_SET_PARAM
from hope_dedup_engine.apps.public_api.models import DeduplicationSet
from hope_dedup_engine.apps.public_api.models.deduplication import Image
from hope_dedup_engine.apps.public_api.serializers import DeduplicationSetSerializer, ImageSerializer
from hope_dedup_engine.apps.public_api.utils import delete_model_data, start_processing

MESSAGE = "message"
STARTED = "started"
RETRYING = "retrying"
ALREADY_PROCESSING = "already processing"


class DeduplicationSetViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = IsAuthenticated, AssignedToExternalSystem, UserAndDeduplicationSetAreOfTheSameSystem
    serializer_class = DeduplicationSetSerializer

    def get_queryset(self) -> QuerySet:
        return DeduplicationSet.objects.filter(external_system=self.request.user.external_system, deleted=False)

    def perform_create(self, serializer: Serializer) -> None:
        serializer.save(created_by=self.request.user, external_system=self.request.user.external_system)

    def perform_destroy(self, instance: DeduplicationSet) -> None:
        instance.updated_by = self.request.user
        instance.deleted = True
        instance.save()
        delete_model_data(instance)

    @action(detail=True, methods=(HTTPMethod.POST,))
    def process(self, request: Request, pk: UUID | None = None) -> Response:
        deduplication_set = DeduplicationSet.objects.get(pk=pk)
        match deduplication_set.state:
            case DeduplicationSet.State.CLEAN | DeduplicationSet.State.ERROR:
                start_processing(deduplication_set)
                return Response({MESSAGE: RETRYING})
            case DeduplicationSet.State.DIRTY:
                start_processing(deduplication_set)
                return Response({MESSAGE: STARTED})
            case DeduplicationSet.State.PROCESSING:
                return Response({MESSAGE: ALREADY_PROCESSING}, status=status.HTTP_400_BAD_REQUEST)


class ImageViewSet(
    nested_viewsets.NestedViewSetMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = IsAuthenticated, AssignedToExternalSystem, UserAndDeduplicationSetAreOfTheSameSystem
    serializer_class = ImageSerializer
    queryset = Image.objects.all()
    parent_lookup_kwargs = {
        DEDUPLICATION_SET_PARAM: DEDUPLICATION_SET_FILTER,
    }

    def perform_create(self, serializer: Serializer) -> None:
        super().perform_create(serializer)
        deduplication_set = serializer.instance.deduplication_set
        deduplication_set.state = DeduplicationSet.State.DIRTY
        deduplication_set.updated_by = self.request.user
        deduplication_set.save()

    def perform_destroy(self, instance: Image) -> None:
        deduplication_set = instance.deduplication_set
        super().perform_destroy(instance)
        deduplication_set.state = DeduplicationSet.State.DIRTY
        deduplication_set.updated_by = self.request.user
        deduplication_set.save()


@dataclass
class ListDataWrapper:
    data: list[dict]

    def __setitem__(self, key: str, value: Any) -> None:
        for item in self.data:
            item[key] = value


class WrapRequestDataMixin:
    def initialize_request(self, request: Request, *args: Any, **kwargs: Any) -> Request:
        request = super().initialize_request(request, *args, **kwargs)
        request._full_data = ListDataWrapper(request.data)
        return request


class UnwrapRequestDataMixin:
    def initialize_request(self, request: Request, *args: Any, **kwargs: Any) -> Request:
        request = super().initialize_request(request, *args, **kwargs)
        request._full_data = request._full_data.data
        return request


# drf-nested-routers doesn't work correctly when request data is a list, so we use WrapRequestDataMixin,
# UnwrapRequestDataMixin, and ListDataWrapper to make it work with list of objects
class BulkImageViewSet(
    UnwrapRequestDataMixin,
    nested_viewsets.NestedViewSetMixin,
    WrapRequestDataMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = IsAuthenticated, AssignedToExternalSystem, UserAndDeduplicationSetAreOfTheSameSystem
    serializer_class = ImageSerializer
    queryset = Image.objects.all()
    parent_lookup_kwargs = {
        DEDUPLICATION_SET_PARAM: DEDUPLICATION_SET_FILTER,
    }

    def get_serializer(self, *args: Any, **kwargs: Any) -> Serializer:
        return super().get_serializer(*args, **kwargs, many=True)

    def perform_create(self, serializer: Serializer) -> None:
        super().perform_create(serializer)
        if deduplication_set := serializer.instance[0].deduplication_set if serializer.instance else None:
            deduplication_set.updated_by = self.request.user
            deduplication_set.save()

    @action(detail=False, methods=(HTTPMethod.DELETE,))
    def clear(self, request: Request, deduplication_set_pk: str) -> Response:
        deduplication_set = DeduplicationSet.objects.get(pk=deduplication_set_pk)
        Image.objects.filter(deduplication_set=deduplication_set).delete()
        deduplication_set.updated_by = request.user
        deduplication_set.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
