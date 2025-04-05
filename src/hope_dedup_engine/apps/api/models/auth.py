from django.conf import settings
from django.db import models

from rest_framework.authtoken.models import Token


class HDEToken(Token):
    """
    Token model for user to integrate with HOPE
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="auth_tokens", on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_hex(20)
        super().save(*args, **kwargs)
