import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="BiographicGroup",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("business_area", models.CharField(db_index=True, help_text="Business area slug.", max_length=100)),
                ("program_id", models.CharField(db_index=True, help_text="Program id.", max_length=100)),
                ("name", models.CharField(blank=True, help_text="Optional group name.", max_length=128, null=True)),
                (
                    "settings",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Settings shared by datasets in this group.",
                    ),
                ),
                (
                    "processing_locked",
                    models.BooleanField(
                        default=False,
                        help_text="Whether a deduplication task is currently running for this program.",
                    ),
                ),
                ("deleted", models.BooleanField(default=False, help_text="Whether this group was deleted.")),
            ],
            options={
                "permissions": [("release_processing_lock", "Can release processing lock")],
            },
        ),
        migrations.CreateModel(
            name="BiographicSet",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("deduplicating", "Deduplicating"),
                            ("deduplicated", "Deduplicated"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        db_index=True,
                        default="pending",
                        help_text="Dataset state.",
                        max_length=32,
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        help_text="Program group this dataset belongs to.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sets",
                        to="biographic.biographicgroup",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="BiographicRecord",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "reference_pk",
                    models.CharField(
                        help_text="Country Workspace individual ID, or a HOPE UUID for migrated data.",
                        max_length=100,
                    ),
                ),
                (
                    "full_name",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="Denormalized from the payload for admin search. Never used for matching.",
                        max_length=255,
                    ),
                ),
                ("payload", models.JSONField(help_text="Scoreable biographic fields.")),
                (
                    "payload_version",
                    models.PositiveSmallIntegerField(default=1, help_text="Payload schema version."),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, help_text="Date and time when this record was created."),
                ),
                (
                    "dataset",
                    models.ForeignKey(
                        help_text="Dataset this person belongs to.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="records",
                        to="biographic.biographicset",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="BiographicFinding",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "matched_reference_pk",
                    models.CharField(
                        help_text=(
                            "Reference id of the matched person. Not a foreign key: the match may belong "
                            "to another dataset or be a migrated HOPE UUID."
                        ),
                        max_length=100,
                    ),
                ),
                ("score", models.FloatField(help_text="Match score.")),
                (
                    "proximity_to_score",
                    models.FloatField(help_text="Score minus the duplicate threshold."),
                ),
                (
                    "status_code",
                    models.CharField(
                        choices=[("duplicate", "Duplicate")],
                        default="duplicate",
                        help_text="Duplicate. Not a biometric face status code.",
                        max_length=32,
                    ),
                ),
                (
                    "scope",
                    models.CharField(
                        choices=[("batch", "Batch"), ("population", "Population")],
                        help_text="Batch or approved-population match. Used for abort counts, not returned to HOPE.",
                        max_length=32,
                    ),
                ),
                (
                    "config",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Snapshot of the settings used when this finding was created.",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, help_text="Date and time when this finding was updated."),
                ),
                (
                    "record",
                    models.ForeignKey(
                        help_text="Person this match was found for.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="findings",
                        to="biographic.biographicrecord",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="biographicgroup",
            constraint=models.UniqueConstraint(
                fields=("business_area", "program_id"),
                name="unique_biographic_group_business_area_program",
            ),
        ),
        migrations.AddConstraint(
            model_name="biographicset",
            constraint=models.UniqueConstraint(
                condition=models.Q(state__in=["deduplicating", "deduplicated"]),
                fields=("group",),
                name="unique_active_biographic_set_per_group",
            ),
        ),
        migrations.AddConstraint(
            model_name="biographicrecord",
            constraint=models.UniqueConstraint(
                fields=("dataset", "reference_pk"),
                name="unique_biographic_record_reference_pk_per_dataset",
            ),
        ),
    ]
