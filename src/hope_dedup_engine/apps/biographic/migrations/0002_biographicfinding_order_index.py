from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    # CREATE INDEX CONCURRENTLY cannot run inside a transaction.
    atomic = False

    dependencies = [("biographic", "0001_initial")]

    operations = [
        AddIndexConcurrently(
            model_name="biographicfinding",
            index=models.Index(fields=["dataset", "-score", "-id"], name="biographic_finding_order_idx"),
        ),
    ]
