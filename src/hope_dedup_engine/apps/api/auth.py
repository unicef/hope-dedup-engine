from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import View

from hope_dedup_engine.apps.api.const import DEDUPLICATION_SET_GROUP_PARAM, GROUP_REFERENCE_PK
from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.auth import HDEToken


CAN_USE_API_PERMISSION = "api.can_use_api"


class CanUseApi(BasePermission):
    def has_permission(self, request: Request, view: View) -> bool:
        return request.user.has_perm(CAN_USE_API_PERMISSION)


class HasAccessToDeduplicationSet(BasePermission):
    def get_group_reference_pk(self, view: View) -> str | None:
        return view.kwargs.get(DEDUPLICATION_SET_GROUP_PARAM) or view.kwargs.get(GROUP_REFERENCE_PK)

    def get_deduplication_set(self, group_reference_pk: str) -> DeduplicationSet | None:
        return (
            DeduplicationSet.objects.filter(group__reference_pk=group_reference_pk, group__deleted=False)
            .exclude(state=DeduplicationSet.State.INACTIVE)
            .first()
        )

    def has_permission(self, request: Request, view: View) -> bool:
        if (group_reference_pk := self.get_group_reference_pk(view)) and (
            deduplication_set := self.get_deduplication_set(group_reference_pk)
        ):
            return deduplication_set.group.system == request.auth.system
        return True


class HDETokenAuthentication(TokenAuthentication):
    model = HDEToken
