"""Encoding.filename: TextField -> FileField (images storage).

Now that 0072 has removed oversized rows in a separate transaction, we can
safely alter the column type to varchar(255) with FileField semantics.

The storage/upload_to callables are defined locally so this historical
migration stays importable after the model reverts `filename` back to a
TextField in 0074 (the model module no longer exposes these helpers).
"""

from django.core.files.storage import FileSystemStorage, InvalidStorageError, storages
from django.db import migrations, models


def _images_storage():
    # The `images` storage alias existed only while images were stored on local
    # disk. It has since been removed (images are read from the shared HOPE blob
    # again), so fall back to a plain FileSystemStorage to keep this historical
    # migration importable/runnable. The storage is never used for file I/O here
    # since 0074 immediately reverts `filename` back to a TextField.
    try:
        return storages["images"]
    except InvalidStorageError:
        return FileSystemStorage()


def encoding_image_upload_to(instance, filename):
    group_ref = instance.deduplication_set.group.reference_pk
    return f"images/{group_ref}/{instance.deduplication_set_id}/{filename}"


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0072_encoding_drop_inline_payloads"),
    ]

    operations = [
        migrations.AlterField(
            model_name="encoding",
            name="filename",
            field=models.FileField(
                help_text="Image file backing this encoding (stored via the `images` Django storage alias).",
                max_length=255,
                storage=_images_storage,
                upload_to=encoding_image_upload_to,
            ),
        ),
    ]
