
import os
import logging
import pathlib

from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.db.backends.signals import connection_created

from PyHardLinkBackup.phlb.human import dt2naturaltimesince
from PyHardLinkBackup.phlb.pathlib2 import Path2
from PyHardLinkBackup.phlb.config import phlb_config

log = logging.getLogger("phlb.%s" % __name__)


def setup_sqlite(sender, connection, **kwargs):
    if connection.vendor == 'sqlite':
        cursor = connection.cursor()
        pragmas = (
            "PRAGMA journal_mode = MEMORY;",
            "PRAGMA temp_store = MEMORY;",
            "PRAGMA synchronous = OFF;"
        )
        for pragma in pragmas:
            log.info("Execute: '%s'" % pragma)
            cursor.execute(pragma)

connection_created.connect(setup_sqlite)


class BackupRun(models.Model):
    """
    One Backup run prefix: start time + backup name
    """
    name = models.CharField(max_length=1024, editable=False,
        help_text=_("The name of the backup directory")
    )
    backup_datetime = models.DateTimeField(auto_now=False, auto_now_add=False, editable=False, unique=True,
        help_text=_("backup_datetime of a started backup. Used in all path as prefix.")
    )
    completed = models.BooleanField(default=False, editable=False,
        help_text=_("Was this backup run finished ?")
    )

    def path_part(self):
        return Path2(
            phlb_config.backup_path,
            self.name,
            self.backup_datetime.strftime(phlb_config.sub_dir_formatter)
        )

    def __str__(self):
        if self.completed:
            complete = "Completed Backup"
        else:
            complete = "*Unfinished* Backup"
        return "%s %r from: %s stored: %r" % (
            complete, self.name,
            dt2naturaltimesince(self.backup_datetime),
            self.path_part().path,
        )

    class Meta:
        ordering = ["-backup_datetime"]
        get_latest_by = "backup_datetime"


class BackupDir(models.Model):
    """
    Unique sub path of backup files.
    """
    directory = models.CharField(max_length=1024, editable=False, unique=True,
        help_text=_("The path in the backup without datetime and filename")
    )

    def path_part(self):
        return Path2(self.directory)

    def __str__(self):
        return self.path_part().path


class BackupFilename(models.Model):
    """
    Unique Filename.
    """
    filename = models.CharField(max_length=1024, editable=False, unique=True,
        help_text=_("Filename of one file in backup")
    )

    def path_part(self):
        return Path2(self.filename)

    def __str__(self):
        return self.path_part().path


class ContentInfo(models.Model):
    hash_hexdigest = models.CharField(
        max_length=128, editable=False, unique=True,
        help_text=_("Hash (hexdigest) of the file content")
    )
    file_size = models.PositiveIntegerField(editable=False,
        help_text=_("The file size in Bytes")
    )

    def __str__(self):
        return "Hash: %s...%s File Size: %i Bytes" % (
            self.hash_hexdigest[:4], self.hash_hexdigest[-4:], self.file_size
        )


class BackupEntryManager(models.Manager):
    def create(self, backup_run, directory, filename, hash_hexdigest, file_stat):
        log.debug(
            "Save: %r %r %r %r %r",
            backup_run, directory, filename, hash_hexdigest, file_stat
        )
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
        help_text=_("Time of most recent content modification expressed in nanoseconds as an integer.")
    )
    no_link_source=models.BooleanField(default=False,
        help_text=_("Can this file be used as a hardlink source? (Will be set if a os.link() failed.)")
    )

    objects = BackupEntryManager()

    def get_backup_path(self):
        return Path2(
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
        get_latest_by = "file_mtime_ns"
