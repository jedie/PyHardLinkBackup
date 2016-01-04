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
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('backup_datetime', models.DateTimeField(unique=True, help_text='backup_datetime of a started backup. Used in all path as prefix.', editable=False)),
            ],
        ),
        migrations.CreateModel(
            name='BackupDir',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('directory', models.CharField(unique=True, help_text='The path in the backup without datetime and filename', max_length=1024, editable=False)),
            ],
        ),
        migrations.CreateModel(
            name='BackupEntry',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
            ],
        ),
        migrations.CreateModel(
            name='BackupFilename',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('filename', models.CharField(unique=True, help_text='Filename of one file in backup', max_length=1024, editable=False)),
            ],
        ),
        migrations.CreateModel(
            name='BackupName',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('name', models.CharField(unique=True, help_text='The name of the backup direcotry', max_length=1024, editable=False)),
                ('note', models.TextField(help_text='A comment about this backup directory.')),
            ],
        ),
        migrations.CreateModel(
            name='BackupRun',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('backup_datetime', models.ForeignKey(to='backup_app.BackupDatetime')),
                ('name', models.ForeignKey(to='backup_app.BackupName')),
            ],
        ),
        migrations.CreateModel(
            name='FileHash',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('sha512', models.CharField(unique=True, help_text='SHA-512 (hexdigest) of the file content', max_length=1024, editable=False)),
            ],
        ),
        migrations.AddField(
            model_name='backupentry',
            name='backup_run',
            field=models.ForeignKey(to='backup_app.BackupRun'),
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
        migrations.AddField(
            model_name='backupentry',
            name='sha512',
            field=models.ForeignKey(to='backup_app.FileHash'),
        ),
    ]
