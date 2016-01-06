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
import logging

from django.db import models

log = logging.getLogger(__name__)

BACKUP_SUB_FORMAT = "%Y-%m-%d-%H%M%S"


class BackupName(models.Model):
    """
    a name of a backup, e.g.: the last path name
    """
    name = models.CharField(max_length=1024, editable=False, unique=True,
        help_text="The name of the backup directory"
    )
    note = models.TextField(help_text="A comment about this backup directory.")

    def path_part(self):
        return self.name
    __str__ = path_part


class BackupDatetime(models.Model):
    """
    The start time of one backup run.
    Used as a sub directory prefix.
    """
    backup_datetime = models.DateTimeField(auto_now=False, auto_now_add=False, editable=False, unique=True,
        help_text="backup_datetime of a started backup. Used in all path as prefix."
    )
    def path_part(self):
        return self.backup_datetime.strftime(BACKUP_SUB_FORMAT)
    __str__ = path_part


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

    def path_part(self):
        return os.path.join(
            self.name.path_part(),
            self.backup_datetime.path_part()
        )
    __str__ = path_part

    class Meta:
        ordering = ["-backup_datetime"]
        get_latest_by = "-backup_datetime"


class BackupDir(models.Model):
    """
    Unique sub path of backup files.
    """
    directory = models.CharField(max_length=1024, editable=False, unique=True,
        help_text="The path in the backup without datetime and filename"
    )
    def path_part(self):
        return self.directory
    __str__ = path_part


class BackupFilename(models.Model):
    """
    Unique Filename.
    """
    filename = models.CharField(max_length=1024, editable=False, unique=True,
        help_text="Filename of one file in backup"
    )
    def path_part(self):
        return self.filename
    __str__ = path_part


class ContentInfo(models.Model):
    hash_hexdigest = models.CharField(
        max_length=128, editable=False, unique=True,
        help_text="SHA-512 (hexdigest) of the file content"
    )
    file_size = models.PositiveIntegerField(editable=False,
        help_text="The file size in Bytes"
    )

    def __str__(self):
        return "SHA512: %s...%s File Size: %i Bytes" % (
            self.hash_hexdigest[:4], self.hash_hexdigest[-4:], self.file_size
        )


class BackupEntryManager(models.Manager):
    def create(self, backup_run, directory, filename, hash_hexdigest, file_stat):
        log.debug("Save:", backup_run, directory, filename, hash_hexdigest, file_stat)
        directory, created = BackupDir.objects.get_or_create(directory=directory)
        filename, created = BackupFilename.objects.get_or_create(filename=filename)
        content_info, created = ContentInfo.objects.get_or_create(
            hash_hexdigest=hash_hexdigest, file_size=file_stat.st_size
        )

        return super(BackupEntryManager, self).create(
            backup_run=backup_run,
            directory=directory, filename=filename, content_info=content_info,
            file_mtime_ns = file_stat.st_mtime_ns,
        )


class BackupEntry(models.Model):
    backup_run = models.ForeignKey(BackupRun)
    directory = models.ForeignKey(BackupDir)
    filename = models.ForeignKey(BackupFilename)
    content_info = models.ForeignKey(ContentInfo)
    file_mtime_ns = models.PositiveIntegerField(editable=False,
        help_text="Time of most recent content modification expressed in nanoseconds as an integer."
    )
    objects = BackupEntryManager()

    def get_backup_path(self):
        return os.path.join(
            self.backup_run.path_part(),
            self.directory.path_part(),
            self.filename.path_part(),
        )

    def __str__(self):
        return "%s %s mtime:%s" % (
            self.get_backup_path(), self.content_info, self.file_mtime_ns
        )

    class Meta:
        ordering = ["-backup_run__backup_datetime"]
        get_latest_by = "-backup_run__backup_datetime"