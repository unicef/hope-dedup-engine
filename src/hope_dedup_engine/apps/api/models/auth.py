from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from rest_framework.authtoken.models import Token


class HDEToken(Token):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="auth_tokens", on_delete=models.CASCADE, verbose_name=_("User")
    )
