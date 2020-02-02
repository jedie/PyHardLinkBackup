from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("backup_app", "0002_backupentry_no_link_source")]

    operations = [
        migrations.AlterModelOptions(
            name="backupentry",
            options={"ordering": ["-backup_run__backup_datetime"], "get_latest_by": "file_mtime_ns"},
        ),
        migrations.AlterModelOptions(
            name="backuprun", options={"ordering": ["-backup_datetime"], "get_latest_by": "backup_datetime"}
        ),
        migrations.AddField(
            model_name="backuprun",
            name="completed",
            field=models.BooleanField(editable=False, default=False, help_text="Was this backup run finished ?"),
        ),
    ]
