from django.db.models import QuerySet

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from hope_dedup_engine.apps.public_api.auth import AssignedToExternalSystem, HDETokenAuthentication
from hope_dedup_engine.apps.public_api.models import DeduplicationSet
from hope_dedup_engine.apps.public_api.serializers import DeduplicationSetSerializer


class DeduplicationSetViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    authentication_classes = (HDETokenAuthentication,)
    permission_classes = IsAuthenticated, AssignedToExternalSystem
    serializer_class = DeduplicationSetSerializer

    def get_queryset(self) -> QuerySet:
        return DeduplicationSet.objects.filter(external_system=self.request.user.external_system)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, external_system=self.request.user.external_system)
