import logging

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from hope_dedup_engine.apps.api.models import Encoding

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=Encoding)
def delete_encoding_image_file(sender: type[Encoding], instance: Encoding, **kwargs: object) -> None:
    """Remove the image file after the deleting transaction commits.

    ``post_delete`` runs inside the transaction. Deleting the file immediately
    would leave the encoding row pointing at a missing file if that transaction
    rolls back.
    """
    name = instance.filename.name
    if not name:
        return
    storage = instance.filename.storage

    def _delete_file() -> None:
        try:
            storage.delete(name)
        except FileNotFoundError:
            pass
        except Exception:  # noqa: BLE001
            logger.warning("Failed to delete file %s from images storage", name, exc_info=True)

    transaction.on_commit(_delete_file)
