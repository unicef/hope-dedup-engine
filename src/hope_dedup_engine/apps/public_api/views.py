from dataclasses import dataclass
from typing import Any

from django.db.models import QuerySet

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
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
from hope_dedup_engine.apps.public_api.utils import delete_model_data


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


class ImageViewSet(
    nested_viewsets.NestedViewSetMixin, mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
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
