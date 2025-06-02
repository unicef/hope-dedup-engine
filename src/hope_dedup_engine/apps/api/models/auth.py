import secrets

from django.conf import settings
from django.db import models

from rest_framework.authtoken.models import Token


class HDEToken(Token):
    """
    Token model for user to integrate with HOPE
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="auth_tokens", on_delete=models.CASCADE)
    key = models.CharField(max_length=40, primary_key=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.key or self.key.isspace():
            self.key = secrets.token_hex(20)
        super().save(*args, **kwargs)
