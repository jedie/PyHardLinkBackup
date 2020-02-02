from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("backup_app", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="backupentry",
            name="no_link_source",
            field=models.BooleanField(
                default=False,
                help_text="Can this file be used as a hardlink source? (Will be set if a os.link() failed.)",
            ),
        )
    ]
