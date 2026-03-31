from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0065_remove_deduplicationset_unique_active_deduplication_set_per_group_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="encoding",
            name="face_coverage",
        ),
    ]
