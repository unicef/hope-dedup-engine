from django.db import models


class DummyModel(models.Model):
    class Meta:
        managed = False
        verbose_name = "DNN file"
        verbose_name_plural = "DNN files"
