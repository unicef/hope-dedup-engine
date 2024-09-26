from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import DeduplicationSet


@receiver(post_save, sender=DeduplicationSet)
def call_state_setter(sender, instance, created, **kwargs):
    if created:
        instance.state = instance.State.CLEAN
