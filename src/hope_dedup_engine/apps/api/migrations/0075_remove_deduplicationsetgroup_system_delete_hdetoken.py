from django.db import migrations


API_DEDUP_GRANT = "API_DEDUP"


def migrate_hde_tokens(apps, schema_editor) -> None:
    HDEToken = apps.get_model("api", "HDEToken")
    APIToken = apps.get_model("hope_api_auth", "APIToken")
    db = schema_editor.connection.alias
    tokens = list(HDEToken.objects.using(db).iterator())

    if APIToken.objects.using(db).filter(key__in=(token.key for token in tokens)).exists():
        raise RuntimeError("Cannot migrate HDE tokens: token key already exists.")

    APIToken.objects.using(db).bulk_create(
        APIToken(
            key=token.key,
            user_id=token.user_id,
            valid_from=token.created.date(),
            grants=[API_DEDUP_GRANT],
        )
        for token in tokens
    )


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0074_alter_deduplicationsetgroup_options_and_more"),
        ("hope_api_auth", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="deduplicationsetgroup",
            name="system",
        ),
        migrations.RunPython(migrate_hde_tokens),
        migrations.DeleteModel(
            name="HDEToken",
        ),
    ]
