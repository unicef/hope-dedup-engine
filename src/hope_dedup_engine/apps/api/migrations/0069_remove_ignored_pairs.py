from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0068_deduplicationset_log"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="ignoredreferencepkpair",
            name="unique_ignored_ref_pair",
        ),
        migrations.RemoveConstraint(
            model_name="ignoredfilenamepair",
            name="unique_ignored_filename_pair",
        ),
        migrations.DeleteModel(
            name="IgnoredFilenamePair",
        ),
        migrations.DeleteModel(
            name="IgnoredReferencePkPair",
        ),
    ]
