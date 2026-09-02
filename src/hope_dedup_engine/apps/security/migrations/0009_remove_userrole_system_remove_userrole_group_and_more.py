from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0075_remove_deduplicationsetgroup_system_delete_hdetoken"),
        ("security", "0008_delete_externalsystem"),
    ]

    operations = [
        migrations.DeleteModel(
            name="UserRole",
        ),
        migrations.DeleteModel(
            name="System",
        ),
    ]
