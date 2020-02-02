from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("backup_app", "0004_BackupRun_ini_file_20160203_1415")]

    operations = [
        migrations.AlterField(
            model_name="backupdir",
            name="directory",
            field=models.CharField(
                unique=True, help_text="The path in the backup without datetime and filename", max_length=1024
            ),
        ),
        migrations.AlterField(
            model_name="backupentry",
            name="file_mtime_ns",
            field=models.PositiveIntegerField(
                help_text="Time of most recent content modification expressed in nanoseconds as an integer."
            ),
        ),
        migrations.AlterField(
            model_name="backupfilename",
            name="filename",
            field=models.CharField(unique=True, help_text="Filename of one file in backup", max_length=1024),
        ),
        migrations.AlterField(
            model_name="backuprun",
            name="backup_datetime",
            field=models.DateTimeField(
                unique=True, help_text="backup_datetime of a started backup. Used in all path as prefix."
            ),
        ),
        migrations.AlterField(
            model_name="backuprun",
            name="completed",
            field=models.BooleanField(default=False, help_text="Was this backup run finished ?"),
        ),
        migrations.AlterField(
            model_name="backuprun",
            name="name",
            field=models.CharField(help_text="The name of the backup directory", max_length=1024),
        ),
        migrations.AlterField(
            model_name="contentinfo",
            name="file_size",
            field=models.PositiveIntegerField(help_text="The file size in Bytes"),
        ),
        migrations.AlterField(
            model_name="contentinfo",
            name="hash_hexdigest",
            field=models.CharField(unique=True, help_text="Hash (hexdigest) of the file content", max_length=128),
        ),
    ]
