from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0062_remove_unused_job_models"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="deduplicationset",
            name="settings",
        ),
    ]
