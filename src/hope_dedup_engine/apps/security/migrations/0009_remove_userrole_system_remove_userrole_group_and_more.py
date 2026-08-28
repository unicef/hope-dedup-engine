from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0076_remove_deduplicationsetgroup_system_apitoken_and_more"),
        ("security", "0008_delete_externalsystem"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="userrole",
            name="system",
        ),
        migrations.RemoveField(
            model_name="userrole",
            name="group",
        ),
        migrations.RemoveField(
            model_name="userrole",
            name="user",
        ),
        migrations.DeleteModel(
            name="System",
        ),
        migrations.DeleteModel(
            name="UserRole",
        ),
    ]
