from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0061_remove_encoding_api_encodin_dedupli_909c41_idx"),
    ]

    operations = [
        migrations.DeleteModel(
            name="EncodeChunkJob",
        ),
        migrations.DeleteModel(
            name="DeduplicateDatasetJob",
        ),
        migrations.DeleteModel(
            name="CallbackFindingsJob",
        ),
        migrations.DeleteModel(
            name="DedupeChunkJob",
        ),
    ]
