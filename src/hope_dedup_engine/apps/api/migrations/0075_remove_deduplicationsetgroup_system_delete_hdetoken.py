from django.db import migrations, models


API_DEDUP_GRANT = "API_DEDUP"


def remove_legacy_user_unique(apps, schema_editor) -> None:
    APIToken = apps.get_model("hope_api_auth", "APIToken")

    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(cursor, APIToken._meta.db_table)

    for name, constraint in constraints.items():
        if constraint["unique"] and constraint["columns"] == ["user_id"]:
            schema_editor.remove_constraint(APIToken, models.UniqueConstraint(fields=["user"], name=name))


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
        migrations.RunPython(remove_legacy_user_unique),
        migrations.RunPython(migrate_hde_tokens),
        migrations.DeleteModel(
            name="HDEToken",
        ),
    ]
