from django.db import models


class DummyModel(models.Model):
    class Meta:
        managed = False
        verbose_name = "Model weights files"
        verbose_name_plural = "Model weights files"
