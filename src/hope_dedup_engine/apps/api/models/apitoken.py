from django.conf import settings
from django.db import models
from hope_api_auth.models import AbstractAPIToken


class APIToken(AbstractAPIToken):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="auth_tokens", on_delete=models.CASCADE)
