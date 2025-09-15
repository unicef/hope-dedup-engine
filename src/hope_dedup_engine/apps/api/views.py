from dataclasses import dataclass
from http import HTTPMethod
from typing import Any
from uuid import UUID

from django.db.models import Q, QuerySet, Model
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
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
    DEDUPLICATION_SET_FILTER,
    DEDUPLICATION_SET_PARAM,
)
from hope_dedup_engine.apps.api.models import (
    DeduplicationSet,
    Encoding,
    Finding,
    IgnoredFilenamePair,
    IgnoredReferencePkPair,
    Image,
)
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
from hope_dedup_engine.apps.api.utils.process import delete_model_data, start_processing


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
        description="""To launch the deduplication process again, you need to call the `process`
endpoint with a `POST` request.

Here is the command:

```bash
curl -X POST http://localhost:8000/api/deduplication-sets/{id}/process/ \\
-H 'Authorization: Token <your_token>'
```

After running this, the deduplication set's state will change to "Processing",
and the Celery task will start executing.""",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def process(self, request: Request, pk: UUID | None = None) -> Response:
        deduplication_set = self.get_object()
        if deduplication_set.state == DeduplicationSet.State.PROCESSING:
            return Response({"message": "already processing"}, status=status.HTTP_409_CONFLICT)
        start_processing(deduplication_set)
        return Response({"message": "started"})

    @extend_schema(
        request=EmptySerializer,
        responses=EmptySerializer,
        description="""Stop the current task and clear results.
This will terminate the active Celery task, clear any existing findings
or encodings for this set, and reset its state so it can be processed again.

**Example:**
```bash
curl -X POST http://localhost:8000/api/deduplication-sets/{id}/clear_results/ \\
-H 'Authorization: Token <your_token>'
```

You should receive a confirmation message like:
`{"message":"Processing results cleared. You can now start the process again."}`.""",
    )
    @action(detail=True, methods=(HTTPMethod.POST,))
    def clear_results(self, request: Request, pk: UUID | None = None) -> Response:
        deduplication_set = self.get_object()

        # Best-effort attempt to stop any running tasks.
        try:
            if dedup_job := deduplication_set.dedupjob:
                dedup_job.terminate()
                dedup_job.delete()
        except DeduplicationSet.dedupjob.RelatedObjectDoesNotExist:
            pass

        # Clean up derived data
        Encoding.objects.filter(deduplication_set=deduplication_set).delete()
        Finding.objects.filter(deduplication_set=deduplication_set).delete()

        # Reset state to allow reprocessing.
        deduplication_set.set_state(DeduplicationSet.State.MODIFIED)

        return Response({"message": "Processing results cleared. You can now start the process again."})

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


@dataclass
class ListDataWrapper:
    data: list[dict[str, Any]]

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
    nested_viewsets.NestedViewSetMixin[Image],
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
    serializer_class = ImageSerializer
    queryset = Image.objects.all()
    parent_lookup_kwargs = {
        DEDUPLICATION_SET_PARAM: DEDUPLICATION_SET_FILTER,
    }

    def get_serializer(self, *args: Any, **kwargs: Any) -> Serializer:
        if self.action == "create":
            return CreateImageSerializer(*args, **kwargs, many=True)
        return super().get_serializer(*args, **kwargs, many=True)

    def perform_create(self, serializer: Serializer) -> None:
        super().perform_create(serializer)
        if deduplication_set := (serializer.instance[0].deduplication_set if serializer.instance else None):
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


REFERENCE_PK = "reference_pk"


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
    # TODO: Add filters
    queryset = Finding.objects.all()
    parent_lookup_kwargs = {
        DEDUPLICATION_SET_PARAM: DEDUPLICATION_SET_FILTER,
    }

    def get_queryset(self) -> QuerySet[Finding]:
        queryset = super().get_queryset()
        if reference_pk := self.request.query_params.get(REFERENCE_PK):
            return queryset.filter(Q(first_reference_pk=reference_pk) | Q(second_reference_pk=reference_pk))
        return queryset

    @extend_schema(
        description="List all duplicates found in the deduplication set",
        parameters=[
            OpenApiParameter(
                REFERENCE_PK,
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                description="Filters results by reference pk",
            )
        ],
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
