from django.db import models


class DeduplicationSet(models.Model):
    name = models.CharField(max_length=100)
    reference_pk = models.IntegerField()
