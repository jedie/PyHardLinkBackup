#coding: utf-8

import configparser

from django.db import migrations, models

from PyHardLinkBackup.backup_app.models import BackupRun


def forwards_func(apps, schema_editor):
    """
    manage migrate backup_app 0004_BackupRun_ini_file_20160203_1415
    """
    print("\n")
    create_count = 0
    backup_runs = BackupRun.objects.all()
    for backup_run in backup_runs:
        try:
            backup_run.write_config()
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
    backup_runs = BackupRun.objects.all()
    for backup_run in backup_runs:
        config_path = backup_run.get_config_path()
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
