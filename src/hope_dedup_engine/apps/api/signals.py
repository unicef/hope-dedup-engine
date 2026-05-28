import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

from hope_dedup_engine.apps.api.models import Encoding

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=Encoding)
def delete_encoding_image_file(sender, instance: Encoding, **kwargs) -> None:
    """Remove the underlying image file when an Encoding row is deleted."""
    if not instance.filename:
        return
    try:
        instance.filename.delete(save=False)
    except FileNotFoundError:
        pass
    except Exception:  # noqa: BLE001
        logger.warning("Failed to delete file %s from images storage", instance.filename.name, exc_info=True)
