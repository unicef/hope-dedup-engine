from dataclasses import dataclass
from http import HTTPMethod
from typing import Any
from uuid import UUID

from django.db.models import QuerySet

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework_nested import viewsets as nested_viewsets

from hope_dedup_engine.apps.api.auth import (
    AssignedToExternalSystem,
    HDETokenAuthentication,
    UserAndDeduplicationSetAreOfTheSameSystem,
)
from hope_dedup_engine.apps.api.const import (
    DEDUPLICATION_SET_FILTER,
    DEDUPLICATION_SET_PARAM,
)
from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import (
    Duplicate,
    IgnoredKeyPair,
    Image,
)
from hope_dedup_engine.apps.api.serializers import (
    DeduplicationSetSerializer,
    DuplicateSerializer,
    EmptySerializer,
    IgnoredKeyPairSerializer,
    ImageSerializer,
)
from hope_dedup_engine.apps.api.utils import delete_model_data, start_processing


# drf-spectacular uses first non-empty docstring it finds in class mro. When there is no docstring in view class and
# we are using base classes from drf-nested-routers we get documentation for typing.Generic class as resource
# documentation. With the &nbsp; HTML entity we get an empty description for resource, but it looks a little bit
# different when compared with "real" empty description. So we use this base class for all views to have the same look
# for view classes with empty docstrings and different base classes.
class EmptyDocString:
    """&nbsp;"""


class DeduplicationSetViewSet(
    EmptyDocString,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = (
        IsAuthenticated,
        AssignedToExternalSystem,
        UserAndDeduplicationSetAreOfTheSameSystem,
    )
    serializer_class = DeduplicationSetSerializer

    def get_queryset(self) -> QuerySet:
        return DeduplicationSet.objects.filter(
            external_system=self.request.user.external_system, deleted=False
        )

    def perform_create(self, serializer: Serializer) -> None:
        serializer.save(
            created_by=self.request.user,
            external_system=self.request.user.external_system,
        )

    def perform_destroy(self, instance: DeduplicationSet) -> None:
        instance.updated_by = self.request.user
        instance.deleted = True
        instance.save()
        delete_model_data(instance)

    @extend_schema(request=EmptySerializer, responses=EmptySerializer)
    @action(detail=True, methods=(HTTPMethod.POST,))
    def process(self, request: Request, pk: UUID | None = None) -> Response:
        start_processing(DeduplicationSet.objects.get(pk=pk))
        return Response({"message": "started"})


class ImageViewSet(
    EmptyDocString,
    nested_viewsets.NestedViewSetMixin[Image],
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = (
        IsAuthenticated,
        AssignedToExternalSystem,
        UserAndDeduplicationSetAreOfTheSameSystem,
    )
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
    data: list[dict[str, Any]]

    def __setitem__(self, key: str, value: Any) -> None:
        for item in self.data:
            item[key] = value


class WrapRequestDataMixin:
    def initialize_request(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> Request:
        request = super().initialize_request(request, *args, **kwargs)
        request._full_data = ListDataWrapper(request.data)
        return request


class UnwrapRequestDataMixin:
    def initialize_request(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> Request:
        request = super().initialize_request(request, *args, **kwargs)
        request._full_data = request._full_data.data
        return request


# drf-nested-routers doesn't work correctly when request data is a list, so we use WrapRequestDataMixin,
# UnwrapRequestDataMixin, and ListDataWrapper to make it work with list of objects
class BulkImageViewSet(
    EmptyDocString,
    UnwrapRequestDataMixin,
    nested_viewsets.NestedViewSetMixin[Image],
    WrapRequestDataMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = (
        IsAuthenticated,
        AssignedToExternalSystem,
        UserAndDeduplicationSetAreOfTheSameSystem,
    )
    serializer_class = ImageSerializer
    queryset = Image.objects.all()
    parent_lookup_kwargs = {
        DEDUPLICATION_SET_PARAM: DEDUPLICATION_SET_FILTER,
    }

    def get_serializer(self, *args: Any, **kwargs: Any) -> Serializer:
        return super().get_serializer(*args, **kwargs, many=True)

    def perform_create(self, serializer: Serializer) -> None:
        super().perform_create(serializer)
        if deduplication_set := (
            serializer.instance[0].deduplication_set if serializer.instance else None
        ):
            deduplication_set.updated_by = self.request.user
            deduplication_set.save()

    @action(detail=False, methods=(HTTPMethod.DELETE,))
    def clear(self, request: Request, deduplication_set_pk: str) -> Response:
        deduplication_set = DeduplicationSet.objects.get(pk=deduplication_set_pk)
        Image.objects.filter(deduplication_set=deduplication_set).delete()
        deduplication_set.updated_by = request.user
        deduplication_set.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DuplicateViewSet(
    EmptyDocString,
    nested_viewsets.NestedViewSetMixin[Duplicate],
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = (
        IsAuthenticated,
        AssignedToExternalSystem,
        UserAndDeduplicationSetAreOfTheSameSystem,
    )
    serializer_class = DuplicateSerializer
    queryset = Duplicate.objects.all()
    parent_lookup_kwargs = {
        DEDUPLICATION_SET_PARAM: DEDUPLICATION_SET_FILTER,
    }


class IgnoredKeyPairViewSet(
    EmptyDocString,
    nested_viewsets.NestedViewSetMixin[IgnoredKeyPair],
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = (
        IsAuthenticated,
        AssignedToExternalSystem,
        UserAndDeduplicationSetAreOfTheSameSystem,
    )
    serializer_class = IgnoredKeyPairSerializer
    queryset = IgnoredKeyPair.objects.all()
    parent_lookup_kwargs = {
        DEDUPLICATION_SET_PARAM: DEDUPLICATION_SET_FILTER,
    }

    def perform_create(self, serializer: Serializer) -> None:
        super().perform_create(serializer)
        deduplication_set = serializer.instance.deduplication_set
        deduplication_set.state = DeduplicationSet.State.DIRTY
        deduplication_set.updated_by = self.request.user
        deduplication_set.save()
