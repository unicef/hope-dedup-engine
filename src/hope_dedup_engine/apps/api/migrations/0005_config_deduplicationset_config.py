# Generated by Django 5.0.7 on 2024-09-24 09:05

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0004_remove_deduplicationset_error_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Config",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("face_distance_threshold", models.FloatField(null=True)),
            ],
        ),
        migrations.AddField(
            model_name="deduplicationset",
            name="config",
            field=models.OneToOneField(
                null=True, on_delete=django.db.models.deletion.SET_NULL, to="api.config"
            ),
        ),
    ]