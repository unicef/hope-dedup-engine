from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0074_alter_encoding_embedding_status_code_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="deduplicationsetgroup",
            options={"permissions": [("release_processing_lock", "Can release processing lock")]},
        ),
    ]
