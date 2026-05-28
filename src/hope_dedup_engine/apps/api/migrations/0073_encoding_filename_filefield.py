"""Encoding.filename: TextField -> FileField (images storage).

Now that 0072 has removed oversized rows in a separate transaction, we can
safely alter the column type to varchar(255) with FileField semantics.
"""

from django.db import migrations, models

import hope_dedup_engine.apps.api.models.deduplication


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
                storage=hope_dedup_engine.apps.api.models.deduplication._images_storage,
                upload_to=hope_dedup_engine.apps.api.models.deduplication.encoding_image_upload_to,
            ),
        ),
    ]
