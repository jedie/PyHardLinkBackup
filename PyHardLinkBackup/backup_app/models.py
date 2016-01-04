"""
    The complete backup path:

    destination/name/backup_datetime/sub/path/filename
    |           |           |               |        |
    |           |           |               |        '-> filename and .hash file
    |           |           |               '-> The path from the source direcotry without prefix and filename
    |           |           '-> Start time of the backup run
    |           '-> Name of this source path
    '-> Prefix path for all backups

"""

import os

from django.db import models


BACKUP_SUB_FORMAT="%Y-%m-%d-%H%M%S"


class BackupName(models.Model):
    """
    a name of a backup, e.g.: the last path name
    """
    name = models.CharField(max_length=1024, editable=False, unique=True,
        help_text="The name of the backup direcotry"
    )
    note = models.TextField(help_text="A comment about this backup directory.")

    def __str__(self):
        return self.name


class BackupDatetime(models.Model):
    """
    The start time of one backup run.
    Used as a sub directory prefix.
    """
    backup_datetime = models.DateTimeField(auto_now=False, auto_now_add=False, editable=False, unique=True,
        help_text="backup_datetime of a started backup. Used in all path as prefix."
    )
    def __str__(self):
        return self.backup_datetime.strftime(BACKUP_SUB_FORMAT)


class BackupRunManager(models.Manager):
    def create(self, name, backup_datetime):
        name, created = BackupName.objects.get_or_create(name=name)
        backup_datetime = BackupDatetime.objects.create(backup_datetime=backup_datetime)

        return super(BackupRunManager, self).create(
            name=name, backup_datetime=backup_datetime,
        )


class BackupRun(models.Model):
    """
    One Backup run prefix: start time + backup name
    """
    name = models.ForeignKey(BackupName)
    backup_datetime = models.ForeignKey(BackupDatetime)

    objects = BackupRunManager()

    def __str__(self):
        return "%s %s" % (self.name, self.backup_datetime)


class BackupDir(models.Model):
    """
    Unique sub path of backup files.
    """
    directory = models.CharField(max_length=1024, editable=False, unique=True,
        help_text="The path in the backup without datetime and filename"
    )
    def __str__(self):
        return self.directory


class BackupFilename(models.Model):
    """
    Unique Filename.
    """
    filename = models.CharField(max_length=1024, editable=False, unique=True,
        help_text="Filename of one file in backup"
    )
    def __str__(self):
        return self.filename


class FileHash(models.Model):
    sha512 = models.CharField(max_length=1024, editable=False, unique=True,
        help_text="SHA-512 (hexdigest) of the file content"
    )
    def __str__(self):
        return self.sha512


class BackupEntryManager(models.Manager):
    def create(self, backup_run, directory, filename, sha512):
        print("Save:", backup_run, directory, filename, hash)
        directory, created = BackupDir.objects.get_or_create(directory=directory)
        filename, created = BackupFilename.objects.get_or_create(filename=filename)
        sha512, created = FileHash.objects.get_or_create(sha512=sha512)

        return super(BackupEntryManager, self).create(
            backup_run=backup_run,
            directory=directory, filename=filename, sha512=sha512
        )


class BackupEntry(models.Model):
    backup_run = models.ForeignKey(BackupRun)
    directory = models.ForeignKey(BackupDir)
    filename = models.ForeignKey(BackupFilename)
    sha512 = models.ForeignKey(FileHash)

    objects = BackupEntryManager()

    def __str__(self):
        return "%s %s %s" % (
            self.backup_run,
            os.path.join(str(self.directory), str(self.filename)),
            self.sha512
        )