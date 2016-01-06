# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BackupDatetime',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('backup_datetime', models.DateTimeField(unique=True, help_text='backup_datetime of a started backup. Used in all path as prefix.', editable=False)),
            ],
        ),
        migrations.CreateModel(
            name='BackupDir',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('directory', models.CharField(unique=True, help_text='The path in the backup without datetime and filename', editable=False, max_length=1024)),
            ],
        ),
        migrations.CreateModel(
            name='BackupEntry',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('file_mtime_ns', models.PositiveIntegerField(help_text='Time of most recent content modification expressed in nanoseconds as an integer.', editable=False)),
            ],
            options={
                'ordering': ['-backup_run__backup_datetime'],
                'get_latest_by': '-backup_run__backup_datetime',
            },
        ),
        migrations.CreateModel(
            name='BackupFilename',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('filename', models.CharField(unique=True, help_text='Filename of one file in backup', editable=False, max_length=1024)),
            ],
        ),
        migrations.CreateModel(
            name='BackupName',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('name', models.CharField(unique=True, help_text='The name of the backup directory', editable=False, max_length=1024)),
                ('note', models.TextField(help_text='A comment about this backup directory.')),
            ],
        ),
        migrations.CreateModel(
            name='BackupRun',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('backup_datetime', models.ForeignKey(to='backup_app.BackupDatetime')),
                ('name', models.ForeignKey(to='backup_app.BackupName')),
            ],
            options={
                'ordering': ['-backup_datetime'],
                'get_latest_by': '-backup_datetime',
            },
        ),
        migrations.CreateModel(
            name='ContentInfo',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('hash_hexdigest', models.CharField(unique=True, help_text='SHA-512 (hexdigest) of the file content', editable=False, max_length=128)),
                ('file_size', models.PositiveIntegerField(help_text='The file size in Bytes', editable=False)),
            ],
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
