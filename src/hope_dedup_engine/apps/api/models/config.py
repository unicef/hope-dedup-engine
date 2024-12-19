from django.db import models


class Config(models.Model):
    name = models.CharField(
        max_length=128, unique=True, null=True, blank=True, db_index=True
    )
    settings = models.JSONField(default=dict, null=True, blank=True)

    def __str__(self) -> str:
        return self.name or f"ID: {self.pk}"

    # def clean(self) -> None:
    #     try:
    #         schema = SchemaManager.get_or_create()
    #         DefaultValidatingValidator(schema).validate(self.settings)
    #     except Exception as e:
    #         raise ValidationError({"settings": e.message})
