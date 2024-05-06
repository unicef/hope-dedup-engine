from django.db.models import QuerySet

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import Serializer

from hope_dedup_engine.apps.public_api.auth import AssignedToExternalSystem, HDETokenAuthentication
from hope_dedup_engine.apps.public_api.models import DeduplicationSet
from hope_dedup_engine.apps.public_api.serializers import DeduplicationSetSerializer
from hope_dedup_engine.apps.public_api.utils import delete_model_data


class DeduplicationSetViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = IsAuthenticated, AssignedToExternalSystem
    serializer_class = DeduplicationSetSerializer

    def get_queryset(self) -> QuerySet:
        return DeduplicationSet.objects.filter(external_system=self.request.user.external_system, deleted=False)

    def perform_create(self, serializer: Serializer) -> None:
        serializer.save(created_by=self.request.user, external_system=self.request.user.external_system)

    def perform_destroy(self, instance: DeduplicationSet) -> None:
        instance.deleted = True
        instance.save()
        delete_model_data(instance)
