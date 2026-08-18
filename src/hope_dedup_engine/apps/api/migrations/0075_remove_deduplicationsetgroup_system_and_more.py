import django.db.models.deletion
import django.utils.timezone
import hope_api_auth.fields
from django.conf import settings
from django.db import migrations, models


API_DEDUP_GRANT = "API_DEDUP"


def migrate_hde_tokens(apps, schema_editor) -> None:
    HDEToken = apps.get_model("api", "HDEToken")
    APIToken = apps.get_model("api", "APIToken")
    db = schema_editor.connection.alias

    APIToken.objects.using(db).bulk_create(
        [
            APIToken(
                key=token.key,
                user_id=token.user_id,
                valid_from=token.created.date(),
                grants=[API_DEDUP_GRANT],
            )
            for token in HDEToken.objects.using(db).all()
        ]
    )


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0074_alter_encoding_embedding_status_code_and_finding_status_code"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name="deduplicationsetgroup",
            name="system",
        ),
        migrations.CreateModel(
            name="APIToken",
            fields=[
                (
                    "created",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created"),
                ),
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "key",
                    models.CharField(max_length=40, unique=True, verbose_name="Key"),
                ),
                (
                    "allowed_ips",
                    models.CharField(blank=True, max_length=200, null=True, verbose_name="IPs"),
                ),
                ("valid_from", models.DateField(default=django.utils.timezone.now)),
                ("valid_to", models.DateField(blank=True, null=True)),
                (
                    "grants",
                    hope_api_auth.fields.ChoiceArrayField(base_field=models.CharField(max_length=255), size=None),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="auth_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.RunPython(migrate_hde_tokens),
        migrations.DeleteModel(
            name="HDEToken",
        ),
    ]
