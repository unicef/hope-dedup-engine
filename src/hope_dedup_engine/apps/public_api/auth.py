from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import BasePermission

from hope_dedup_engine.apps.public_api.models.auth import HDEToken


class AssignedToExternalSystem(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.external_system


class HDETokenAuthentication(TokenAuthentication):
    model = HDEToken
