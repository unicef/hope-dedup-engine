from django.core.exceptions import ValidationError
from django.db import models

from jsonschema import ValidationError as JSONSchemaValidationError

from hope_dedup_engine.apps.api.utils.config_schema import (
    DefaultValidatingValidator,
    settings_schema,
)


class Config(models.Model):
    name = models.CharField(
        max_length=128, unique=True, null=True, blank=True, db_index=True
    )
    settings = models.JSONField(default=dict, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name}" if self.name else f"ID: {self.pk}"

    def clean(self) -> None:
        try:
            DefaultValidatingValidator(settings_schema).validate(self.settings)
        except JSONSchemaValidationError as e:
            raise ValidationError({"settings": e.message})
