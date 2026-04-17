"""
Refactor DeduplicationSet states (phase 1).

Drop old constraint, add processing_locked field, migrate state data,
update field choices.

Old states → New states mapping:
  READY (0)      → READY (2)
  MODIFIED (1)   → READY (2)
  PROCESSING (2) → ENCODING_FAILED (5)   -- safest for in-flight jobs
  FAILED (3)     → ENCODING_FAILED (5)
  INACTIVE (4)   → APPROVED (9)
  REJECTED (5)   → REJECTED (10)
"""

from typing import Final

from django.db import migrations, models


OLD_TO_NEW: Final[dict[int, int]] = {
    0: 2,  # READY → READY
    1: 2,  # MODIFIED → READY
    2: 5,  # PROCESSING → ENCODING_FAILED
    3: 5,  # FAILED → ENCODING_FAILED
    4: 9,  # INACTIVE → APPROVED
    5: 10,  # REJECTED → REJECTED
}


def migrate_states_forward(apps, schema_editor):
    DeduplicationSet = apps.get_model("api", "DeduplicationSet")
    for old_val, new_val in OLD_TO_NEW.items():
        DeduplicationSet.objects.filter(state=old_val).update(state=new_val)


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0069_remove_ignored_pairs"),
    ]

    operations = [
        # 1. Drop old constraint (references old state values)
        migrations.RemoveConstraint(
            model_name="deduplicationset",
            name="unique_active_deduplication_set_per_group",
        ),
        # 2. Add processing_locked field to group
        migrations.AddField(
            model_name="deduplicationsetgroup",
            name="processing_locked",
            field=models.BooleanField(
                default=False,
                help_text="Whether any deduplication task is currently running for this group.",
            ),
        ),
        # 3. Migrate state data
        migrations.RunPython(
            migrate_states_forward,
            migrations.RunPython.noop,
        ),
        # 4. Update state field choices
        migrations.AlterField(
            model_name="deduplicationset",
            name="state",
            field=models.IntegerField(
                choices=[
                    (0, "Empty"),
                    (1, "Uploading in progress"),
                    (2, "Ready"),
                    (3, "Encoding in progress"),
                    (4, "Encoded"),
                    (5, "Encoding failed"),
                    (6, "Deduplication in progress"),
                    (7, "Deduplicated"),
                    (8, "Deduplication failed"),
                    (9, "Approved"),
                    (10, "Rejected"),
                ],
                db_column="state",
                default=0,
                help_text="Deduplication set state.",
            ),
        ),
    ]
