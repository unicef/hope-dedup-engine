from django.conf import settings
from django.db import models

from hope_dedup_engine.apps.security.models import ExternalSystem


class DeduplicationSet(models.Model):
    name = models.CharField(max_length=100)
    reference_pk = models.IntegerField()

    external_system = models.ForeignKey(ExternalSystem, on_delete=models.CASCADE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
