from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import View
from hope_dedup_engine.apps.api.models.auth import HDEToken


CAN_USE_API_PERMISSION = "api.can_use_api"


class CanUseApi(BasePermission):
    def has_permission(self, request: Request, view: View) -> bool:
        return request.user.has_perm(CAN_USE_API_PERMISSION)


class HDETokenAuthentication(TokenAuthentication):
    model = HDEToken
