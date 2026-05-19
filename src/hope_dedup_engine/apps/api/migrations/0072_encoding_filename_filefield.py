"""Encoding.filename: TextField -> FileField (images storage).

The previous TextField stored either an Azure-hope key or an inline base64
data URL. Ingest now decodes base64 once and saves the bytes to the `images`
Django storage alias, so the column only needs to hold a storage key
(varchar(255) is plenty).

Rows whose filename is an inline base64 data URL (or any value longer than 255
chars) cannot survive the column type change and must be deleted before the
AlterField runs. Plain filename-style rows (short storage keys) are kept.

Migrations run against the historical model, so the post_delete signal
registered on the live Encoding class does not fire here -- the cleanup is a
pure SQL delete and will not attempt to remove anything from storage.
"""

from django.db import migrations, models
from django.db.models import Q
from django.db.models.functions import Length

import hope_dedup_engine.apps.api.models.deduplication


def _drop_inline_payloads(apps, schema_editor):
    Encoding = apps.get_model("api", "Encoding")
    Encoding.objects.annotate(_len=Length("filename")).filter(
        Q(filename__startswith="data:") | Q(_len__gt=255)
    ).delete()


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0071_deduplication_state_constraint"),
    ]

    operations = [
        migrations.RunPython(_drop_inline_payloads, _noop_reverse),
        migrations.AlterField(
            model_name="encoding",
            name="filename",
            field=models.FileField(
                help_text="Image file backing this encoding (stored via the `images` Django storage alias).",
                max_length=255,
                storage=hope_dedup_engine.apps.api.models.deduplication._images_storage,
                upload_to=hope_dedup_engine.apps.api.models.deduplication.encoding_image_upload_to,
            ),
        ),
    ]
