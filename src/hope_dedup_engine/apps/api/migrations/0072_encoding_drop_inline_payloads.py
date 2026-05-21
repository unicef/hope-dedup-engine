"""Drop Encoding rows that cannot survive the upcoming varchar(255) column change.

Rows whose filename is an inline base64 data URL (or any value longer than 255
chars) are deleted. Plain filename-style rows (short storage keys) are kept.

This is split from the AlterField so that the DELETE and ALTER TABLE run in
separate transactions — PostgreSQL refuses to ALTER a table with pending
trigger events from earlier DML in the same transaction.
"""

from django.db import migrations
from django.db.models import Q
from django.db.models.functions import Length


def _drop_inline_payloads(apps, schema_editor):
    Encoding = apps.get_model("api", "Encoding")
    Encoding.objects.annotate(_len=Length("filename")).filter(
        Q(filename__startswith="data:") | Q(_len__gt=255)
    ).delete()


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0071_deduplication_state_constraint"),
    ]

    operations = [
        migrations.RunPython(_drop_inline_payloads, _noop_reverse),
    ]
