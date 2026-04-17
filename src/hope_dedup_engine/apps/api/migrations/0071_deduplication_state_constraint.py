"""Refactor DeduplicationSet states (phase 2): re-add unique constraint with new excluded states."""

from typing import Final

from django.db import migrations, models

ENCODING_FAILED_STATE: Final[int] = 5
DEDUPLICATION_FAILED_STATE: Final[int] = 8
APPROVED_STATE: Final[int] = 9
REJECTED_STATE: Final[int] = 10


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0070_deduplication_state_refactor"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="deduplicationset",
            constraint=models.UniqueConstraint(
                condition=(
                    ~models.Q(state=ENCODING_FAILED_STATE)
                    & ~models.Q(state=DEDUPLICATION_FAILED_STATE)
                    & ~models.Q(state=APPROVED_STATE)
                    & ~models.Q(state=REJECTED_STATE)
                ),
                fields=("group",),
                name="unique_active_deduplication_set_per_group",
            ),
        ),
    ]
