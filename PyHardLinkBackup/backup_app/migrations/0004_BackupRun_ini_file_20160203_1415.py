# coding: utf-8


from django.db import migrations, models

from PyHardLinkBackup.backup_app.models import BackupRun as OriginBackupRun

def forwards_func(apps, schema_editor):
    """
    manage migrate backup_app 0004_BackupRun_ini_file_20160203_1415
    """
    print("\n")
    create_count = 0
    BackupRun = apps.get_model("backup_app", "BackupRun") # historical version of BackupRun
    backup_runs = BackupRun.objects.all()
    for backup_run in backup_runs:
        # Use the origin BackupRun model to get access to write_config()
        temp = OriginBackupRun(name=backup_run.name, backup_datetime=backup_run.backup_datetime)
        try:
            temp.write_config()
        except OSError as err:
            print("ERROR creating config file: %s" % err)
        else:
            create_count += 1
            # print("%r created." % config_path.path)
    print("%i config files created.\n" % create_count)


def reverse_func(apps, schema_editor):
    """
    manage migrate backup_app 0003_auto_20160127_2002
    """
    print("\n")
    remove_count = 0
    BackupRun = apps.get_model("backup_app", "BackupRun")
    backup_runs = BackupRun.objects.all()
    for backup_run in backup_runs:
        # Use the origin BackupRun model to get access to get_config_path()
        temp = OriginBackupRun(name=backup_run.name, backup_datetime=backup_run.backup_datetime)
        config_path = temp.get_config_path()
        try:
            config_path.unlink()
        except OSError as err:
            print("ERROR removing config file: %s" % err)
        else:
            remove_count += 1
            # print("%r removed." % config_path.path)

    print("%i config files removed.\n" % remove_count)


class Migration(migrations.Migration):
    dependencies = [
        ('backup_app', '0003_auto_20160127_2002'),
    ]
    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]
