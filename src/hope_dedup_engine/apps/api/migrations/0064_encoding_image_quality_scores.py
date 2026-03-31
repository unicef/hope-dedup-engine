from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0063_remove_deduplicationset_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="encoding",
            name="image_quality_scores",
            field=models.JSONField(
                blank=True,
                help_text="OFIQ quality scores dict, e.g. {'Sharpness': 23.4, 'DynamicRange': 88.0}.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="encoding",
            name="embedding_status_code",
            field=models.IntegerField(
                blank=True,
                choices=[
                    (200, "deduplication success"),
                    (404, "no file found"),
                    (412, "no face detected"),
                    (416, "face was detected but did not meet confidence threshold"),
                    (417, "face does not cover sufficient part of the image"),
                    (418, "image quality below threshold"),
                    (429, "multiple faces detected"),
                    (500, "generic error"),
                ],
                help_text="Embedding status code.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="finding",
            name="status_code",
            field=models.IntegerField(
                choices=[
                    (200, "deduplication success"),
                    (404, "no file found"),
                    (412, "no face detected"),
                    (416, "face was detected but did not meet confidence threshold"),
                    (417, "face does not cover sufficient part of the image"),
                    (418, "image quality below threshold"),
                    (429, "multiple faces detected"),
                    (500, "generic error"),
                ],
                default=200,
                help_text="Finding status code.",
            ),
        ),
    ]
