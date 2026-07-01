"""Encoding.filename: FileField -> TextField (shared HOPE blob path/key).

Reverts the local-disk/base64 image storage refactor. `filename` once again
stores a plain path/key into the shared HOPE Azure blob storage; image bytes
are read directly from that storage when needed.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0073_encoding_filename_filefield"),
    ]

    operations = [
        migrations.AlterField(
            model_name="encoding",
            name="filename",
            field=models.TextField(help_text="Filename (path/key) in the shared HOPE blob storage."),
        ),
    ]
