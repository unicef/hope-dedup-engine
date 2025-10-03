from rest_framework import status
from rest_framework.exceptions import APIException
from constance import config


class TooManyReferencePksException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = f"Too many reference pks. Max number allowed: {config.MAX_REFERENCE_PKS_ALLOWED_FOR_FINDINGS}"
