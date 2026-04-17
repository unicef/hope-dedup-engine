from rest_framework import status
from rest_framework.exceptions import APIException
from constance import config


class ConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict."


class TooManyReferencePksException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail=None, code=None):
        if detail is None:
            detail = f"Too many reference pks. Max number allowed: {config.MAX_REFERENCE_PKS_ALLOWED_FOR_FINDINGS}"
        super().__init__(detail=detail, code=code)
