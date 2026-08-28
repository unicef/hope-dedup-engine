from django.db import migrations, models
from django.db.migrations.recorder import MigrationRecorder


class APIToken(models.Model):  # noqa: DJ008
    class Meta:
        app_label = "hope_api_auth_revert"
        db_table = "hope_api_auth_apitoken"
        managed = False


class APILogEntry(models.Model):  # noqa: DJ008
    class Meta:
        app_label = "hope_api_auth_revert"
        db_table = "hope_api_auth_apilogentry"
        managed = False


def revert_hope_api_auth(_apps, schema_editor) -> None:
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))

    if APILogEntry._meta.db_table in tables:
        schema_editor.delete_model(APILogEntry)

    if APIToken._meta.db_table in tables:
        schema_editor.delete_model(APIToken)

    MigrationRecorder(connection).record_unapplied("hope_api_auth", "0001_initial")


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0074_alter_deduplicationsetgroup_options_and_more"),
    ]

    operations = [
        migrations.RunPython(revert_hope_api_auth),
    ]
