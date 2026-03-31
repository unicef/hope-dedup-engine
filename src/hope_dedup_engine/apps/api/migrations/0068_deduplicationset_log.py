from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0067_finding_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="deduplicationset",
            name="log",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Append-only audit log of encoding/deduplication attempts.",
            ),
        ),
    ]
