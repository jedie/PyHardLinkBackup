
import os
import logging

from django.db import models
from django.utils.translation import ugettext_lazy as _

# https://github.com/jedie/django-tools/
from django_tools.fields.directory import DirectoryModelField
from django_tools.fields.sign_separated import SignSeparatedModelField
from django_tools.models import UpdateTimeBaseModel

log = logging.getLogger(__name__)

_DEFAULT_SUB_FORMAT="%Y-%m-%d-%H%M%S"


class Config(UpdateTimeBaseModel):
    name = models.CharField(max_length=1024, editable=False, unique=True,
        help_text=_("The name of the backup directory")
    )
    note = models.TextField(help_text=_("A comment about this backup directory."))

    active=models.BooleanField(
        default=False,
        help_text=_("If not active, then you will always land to change this config on every backup run.")
    )

    backup_path=DirectoryModelField(base_path="",
        default=os.path.expanduser("~/PyHardLinkBackups"),
        help_text=_("Root directory for this backup.")
    )

    hash_name=models.CharField(max_length=128,
        default="sha512",
        help_text=_("Name of the content hasher used in hashlib.new() and as file ending for the hast files.")
    )

    sub_dir_format=models.CharField(max_length=128,
        default=_DEFAULT_SUB_FORMAT,
        help_text=_("datetime.strftime() formatter to create the sub directory.")
    )
    default_new_path_mode=models.CharField(max_length=5,
        default="0o700",
        help_text=_("default directory mode for os.makedirs().")
    )
    chunk_size=models.PositiveIntegerField(
        default=64*1024,
        help_text=_("Size in bytes to read/write files.")
    )
    skip_dirs=SignSeparatedModelField(separator=",", strip_items=True, skip_empty=True,
        default="__pycache__, temp",
        help_text=_("Direcory names that will be recusive exclude vom backups (Comma seperated list!)")
    )
    skip_files=SignSeparatedModelField(separator=",", strip_items=True, skip_empty=True,
        default="*.pyc, *.tmp, *.cache",
        help_text=_("Filename patterns to exclude files from backups use with fnmatch() (Comma seperated list!)")
    )

    def path_part(self):
        return os.path.join(self.backup_path, self.name)
    __str__ = path_part


class BackupDatetime(models.Model):
    """
    The start time of one backup run.
    Used as a sub directory prefix.
    """
    backup_datetime = models.DateTimeField(auto_now=False, auto_now_add=False, editable=False, unique=True,
        help_text=_("backup_datetime of a started backup. Used in all path as prefix.")
    )
    def path_part(self):
        return self.backup_datetime.strftime(_DEFAULT_SUB_FORMAT)
    __str__ = path_part


class BackupRunManager(models.Manager):
    def create(self, name, backup_datetime):
        config, created = Config.objects.get_or_create(name=name)
        backup_datetime = BackupDatetime.objects.create(backup_datetime=backup_datetime)

        return super(BackupRunManager, self).create(
            config=config, backup_datetime=backup_datetime,
        )


class BackupRun(models.Model):
    """
    One Backup run prefix: start time + backup name
    """
    config = models.ForeignKey(Config)
    backup_datetime = models.ForeignKey(BackupDatetime)

    objects = BackupRunManager()

    def path_part(self):
        return os.path.join(
            self.config.path_part(),
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
        help_text=_("The path in the backup without datetime and filename")
    )
    def path_part(self):
        return self.directory
    __str__ = path_part


class BackupFilename(models.Model):
    """
    Unique Filename.
    """
    filename = models.CharField(max_length=1024, editable=False, unique=True,
        help_text=_("Filename of one file in backup")
    )
    def path_part(self):
        return self.filename
    __str__ = path_part


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
        help_text=_("Time of most recent content modification expressed in nanoseconds as an integer.")
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