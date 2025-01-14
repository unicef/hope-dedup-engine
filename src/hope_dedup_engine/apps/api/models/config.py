from django.core.exceptions import ValidationError
from django.db import models

from hope_dedup_engine.apps.api.utils.shema_manager import SchemaManager
from hope_dedup_engine.apps.api.validators import DefaultValidatingValidator


class Config(models.Model):
    name = models.CharField(
        max_length=128, unique=True, null=True, blank=True, db_index=True
    )
    settings = models.JSONField(default=dict, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name}" if self.name else f"ID: {self.pk}"

    def clean(self) -> None:
        try:
            schema = SchemaManager.get_or_create()
            DefaultValidatingValidator(schema).validate(self.settings)
        except Exception as e:
            raise ValidationError({"settings": e.message})
