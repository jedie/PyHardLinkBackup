from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="BackupDir",
            fields=[
                ("id", models.AutoField(verbose_name="ID", auto_created=True, serialize=False, primary_key=True)),
                (
                    "directory",
                    models.CharField(
                        help_text="The path in the backup without datetime and filename",
                        max_length=1024,
                        editable=False,
                        unique=True,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="BackupEntry",
            fields=[
                ("id", models.AutoField(verbose_name="ID", auto_created=True, serialize=False, primary_key=True)),
                (
                    "file_mtime_ns",
                    models.PositiveIntegerField(
                        help_text="Time of most recent content modification expressed in nanoseconds as an integer.",
                        editable=False,
                    ),
                ),
            ],
            options={"ordering": ["-backup_run__backup_datetime"], "get_latest_by": "-backup_run__backup_datetime"},
        ),
        migrations.CreateModel(
            name="BackupFilename",
            fields=[
                ("id", models.AutoField(verbose_name="ID", auto_created=True, serialize=False, primary_key=True)),
                (
                    "filename",
                    models.CharField(
                        help_text="Filename of one file in backup", max_length=1024, editable=False, unique=True
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="BackupRun",
            fields=[
                ("id", models.AutoField(verbose_name="ID", auto_created=True, serialize=False, primary_key=True)),
                (
                    "name",
                    models.CharField(help_text="The name of the backup directory", max_length=1024, editable=False),
                ),
                (
                    "backup_datetime",
                    models.DateTimeField(
                        help_text="backup_datetime of a started backup. Used in all path as prefix.",
                        editable=False,
                        unique=True,
                    ),
                ),
            ],
            options={"ordering": ["-backup_datetime"], "get_latest_by": "-backup_datetime"},
        ),
        migrations.CreateModel(
            name="ContentInfo",
            fields=[
                ("id", models.AutoField(verbose_name="ID", auto_created=True, serialize=False, primary_key=True)),
                (
                    "hash_hexdigest",
                    models.CharField(
                        help_text="Hash (hexdigest) of the file content", max_length=128, editable=False, unique=True
                    ),
                ),
                ("file_size", models.PositiveIntegerField(help_text="The file size in Bytes", editable=False)),
            ],
        ),
        migrations.AddField(
            model_name="backupentry", name="backup_run", field=models.ForeignKey(to="backup_app.BackupRun", on_delete=models.CASCADE)
        ),
        migrations.AddField(
            model_name="backupentry", name="content_info", field=models.ForeignKey(to="backup_app.ContentInfo", on_delete=models.CASCADE)
        ),
        migrations.AddField(
            model_name="backupentry", name="directory", field=models.ForeignKey(to="backup_app.BackupDir", on_delete=models.CASCADE)
        ),
        migrations.AddField(
            model_name="backupentry", name="filename", field=models.ForeignKey(to="backup_app.BackupFilename", on_delete=models.CASCADE)
        ),
    ]
