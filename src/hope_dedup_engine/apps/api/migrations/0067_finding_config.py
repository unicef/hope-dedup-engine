from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0066_remove_encoding_face_coverage"),
    ]

    operations = [
        migrations.AddField(
            model_name="finding",
            name="config",
            field=models.JSONField(
                blank=True,
                help_text="Snapshot of the deduplication settings active when this finding was created.",
                null=True,
            ),
        ),
    ]
