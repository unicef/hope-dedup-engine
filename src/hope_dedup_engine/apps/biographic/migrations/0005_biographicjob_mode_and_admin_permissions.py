from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("biographic", "0004_cleanup_rejected_periodic_task"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="biographicgroup",
            options={
                "permissions": [
                    ("release_processing_lock", "Can release processing lock"),
                    ("rebuild_index", "Can rebuild index"),
                ]
            },
        ),
        migrations.AlterModelOptions(
            name="biographicset",
            options={
                "permissions": [
                    ("send_notification", "Can send notification"),
                    ("process_indexing", "Can index records"),
                    ("process_deduplicate", "Can find duplicates"),
                ]
            },
        ),
        migrations.AddField(
            model_name="biographicjob",
            name="mode",
            field=models.CharField(
                choices=[
                    ("full", "Index and search"),
                    ("index", "Index only"),
                    ("search", "Search only"),
                ],
                default="full",
                help_text="Which steps the run performs. Only an administrator starts a partial run.",
                max_length=16,
            ),
        ),
    ]
