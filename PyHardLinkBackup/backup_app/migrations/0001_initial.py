# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_tools.fields.sign_separated
import django.utils.timezone
import django_tools.fields.directory


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BackupDatetime',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('backup_datetime', models.DateTimeField(unique=True, editable=False, help_text='backup_datetime of a started backup. Used in all path as prefix.')),
            ],
        ),
        migrations.CreateModel(
            name='BackupDir',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('directory', models.CharField(unique=True, editable=False, help_text='The path in the backup without datetime and filename', max_length=1024)),
            ],
        ),
        migrations.CreateModel(
            name='BackupEntry',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('file_mtime_ns', models.PositiveIntegerField(editable=False, help_text='Time of most recent content modification expressed in nanoseconds as an integer.')),
            ],
            options={
                'ordering': ['-backup_run__backup_datetime'],
                'get_latest_by': '-backup_run__backup_datetime',
            },
        ),
        migrations.CreateModel(
            name='BackupFilename',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('filename', models.CharField(unique=True, editable=False, help_text='Filename of one file in backup', max_length=1024)),
            ],
        ),
        migrations.CreateModel(
            name='BackupRun',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('backup_datetime', models.ForeignKey(to='backup_app.BackupDatetime')),
            ],
            options={
                'ordering': ['-backup_datetime'],
                'get_latest_by': '-backup_datetime',
            },
        ),
        migrations.CreateModel(
            name='Config',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('createtime', models.DateTimeField(default=django.utils.timezone.now, editable=False, help_text='Create time')),
                ('lastupdatetime', models.DateTimeField(default=django.utils.timezone.now, editable=False, help_text='Time of the last change.')),
                ('name', models.CharField(unique=True, editable=False, help_text='The name of the backup directory', max_length=1024)),
                ('note', models.TextField(help_text='A comment about this backup directory.')),
                ('active', models.BooleanField(default=False, help_text='If not active, then you will always land to change this config on every backup run.')),
                ('backup_path', django_tools.fields.directory.DirectoryModelField(default='/home/jedie/PyHardLinkBackups', help_text='Root directory for this backup.', max_length=256)),
                ('hash_name', models.CharField(default='sha512', help_text='Name of the content hasher used in hashlib.new() and as file ending for the hast files.', max_length=128)),
                ('sub_dir_format', models.CharField(default='%Y-%m-%d-%H%M%S', help_text='datetime.strftime() formatter to create the sub directory.', max_length=128)),
                ('default_new_path_mode', models.CharField(default='0o700', help_text='default directory mode for os.makedirs().', max_length=5)),
                ('chunk_size', models.PositiveIntegerField(default=65536, help_text='Size in bytes to read/write files.')),
                ('skip_dirs', django_tools.fields.sign_separated.SignSeparatedModelField(default='__pycache__, temp', help_text='Direcory names that will be recusive exclude vom backups (Comma seperated list!)')),
                ('skip_files', django_tools.fields.sign_separated.SignSeparatedModelField(default='*.pyc, *.tmp, *.cache', help_text='Filename patterns to exclude files from backups use with fnmatch() (Comma seperated list!)')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ContentInfo',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('hash_hexdigest', models.CharField(unique=True, editable=False, help_text='Hash (hexdigest) of the file content', max_length=128)),
                ('file_size', models.PositiveIntegerField(editable=False, help_text='The file size in Bytes')),
            ],
        ),
        migrations.AddField(
            model_name='backuprun',
            name='config',
            field=models.ForeignKey(to='backup_app.Config'),
        ),
        migrations.AddField(
            model_name='backupentry',
            name='backup_run',
            field=models.ForeignKey(to='backup_app.BackupRun'),
        ),
        migrations.AddField(
            model_name='backupentry',
            name='content_info',
            field=models.ForeignKey(to='backup_app.ContentInfo'),
        ),
        migrations.AddField(
            model_name='backupentry',
            name='directory',
            field=models.ForeignKey(to='backup_app.BackupDir'),
        ),
        migrations.AddField(
            model_name='backupentry',
            name='filename',
            field=models.ForeignKey(to='backup_app.BackupFilename'),
        ),
    ]
