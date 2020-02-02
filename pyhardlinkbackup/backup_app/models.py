import configparser
import logging

from django.db import models
from django.db.backends.signals import connection_created
from django.utils.translation import ugettext_lazy as _

# https://github.com/jedie/pathlib_revised/
from pathlib_revised import Path2

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.phlb import BACKUP_RUN_CONFIG_FILENAME, INTERNAL_FILES
from pyhardlinkbackup.phlb.config import phlb_config
from pyhardlinkbackup.phlb.humanize import dt2naturaltimesince

log = logging.getLogger(f"phlb.{__name__}")


def setup_sqlite(sender, connection, **kwargs):
    if connection.vendor == "sqlite":
        cursor = connection.cursor()
        pragmas = (
            "PRAGMA journal_mode = MEMORY;",
            "PRAGMA temp_store = MEMORY;",
            "PRAGMA synchronous = OFF;")
        for pragma in pragmas:
            log.info(f"Execute: '{pragma}'")
            cursor.execute(pragma)


connection_created.connect(setup_sqlite)


def build_config_path(backup_path):
    return Path2(backup_path, BACKUP_RUN_CONFIG_FILENAME)


class BackupRunManager(models.Manager):
    def get_from_config_file(self, backup_path):
        if not backup_path.is_dir():
            raise NotADirectoryError(f"Backup path {backup_path.path!r} not found!")

        config_path = build_config_path(backup_path)
        if not config_path.is_file():
            raise FileNotFoundError(f"Config file {config_path.path!r} not found!")

        config = configparser.ConfigParser()
        config.read(config_path.path)

        sections = config.sections()
        if "BACKUP_RUN" not in sections:
            raise KeyError(".ini section 'BACKUP_RUN' not found in: %s" % repr(sections))

        try:
            backup_run_pk = config.getint("BACKUP_RUN", "primary_key")
        except (KeyError, ValueError) as err:
            with config_path.open("r") as f:
                content = f.read().strip()
            raise KeyError(f"{err} in {config_path.path}\nconfig content:\n{content}")

        backup_run = self.get_queryset().get(pk=backup_run_pk)

        if backup_path != backup_run.path_part():
            msg = (
                "Backup path mismatch:\n"
                "From database: %s\n"
                "Current path: %s\n"
                "Maybe the config file pointed to a wrong database entry?!?\n"
                "Used config file: %s"
            ) % (backup_run.path_part(), backup_path, config_path)
            log.error(msg)
            raise AssertionError(msg)

        return backup_run


class BackupRun(models.Model):
    """
    One Backup run prefix: start time + backup name
    """

    name = models.CharField(max_length=1024, help_text=_("The name of the backup directory"))
    backup_datetime = models.DateTimeField(
        auto_now=False,
        auto_now_add=False,
        unique=True,
        help_text=_("backup_datetime of a started backup. Used in all path as prefix."),
    )
    completed = models.BooleanField(default=False, help_text=_("Was this backup run finished ?"))

    objects = BackupRunManager()

    def path_part(self):
        return Path2(
            phlb_config.backup_path,
            self.name,
            self.backup_datetime.strftime(
                phlb_config.sub_dir_formatter))

    def get_config_path(self):
        return build_config_path(self.path_part())

    def make_config(self):
        config = configparser.ConfigParser()
        config["BACKUP_RUN"] = {"primary_key": str(self.pk)}
        return config

    def write_config(self):
        if self.pk is None:
            raise RuntimeError("Save is needed before write config!")

        config_path = self.get_config_path()
        if not config_path.parent.is_dir():
            raise NotADirectoryError(f"Path {config_path.parent.path!r} doesn't exists!")

        config = self.make_config()
        with config_path.open("w") as configfile:
            config.write(configfile)
        log.info(f"BackupRun config written: {config_path}")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.write_config()

    def __str__(self):
        if self.completed:
            complete = "Completed Backup"
        else:
            complete = "*Unfinished* Backup"
        return "{} {!r} from: {} stored: {!r}".format(
            complete,
            self.name,
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

    directory = models.CharField(max_length=1024, unique=True, help_text=_(
        "The path in the backup without datetime and filename"))

    def path_part(self):
        return Path2(self.directory)

    def __str__(self):
        return self.path_part().path


class BackupFilename(models.Model):
    """
    Unique Filename.
    """

    filename = models.CharField(
        max_length=1024,
        unique=True,
        help_text=_("Filename of one file in backup"))

    def save(self, *args, **kwargs):
        # e.g: Test if 'phlb_config.ini' should be added
        assert self.filename not in INTERNAL_FILES  # TODO: Add unittest
        super().save(*args, **kwargs)

    def path_part(self):
        return Path2(self.filename)

    def __str__(self):
        return self.path_part().path


class ContentInfo(models.Model):
    hash_hexdigest = models.CharField(
        max_length=128,
        unique=True,
        help_text=_("Hash (hexdigest) of the file content"))
    file_size = models.PositiveIntegerField(help_text=_("The file size in Bytes"))

    def __str__(self):
        return f"Hash: {self.hash_hexdigest[:4]}...{self.hash_hexdigest[-4:]} File Size: {self.file_size:d} Bytes"


class BackupEntryManager(models.Manager):
    def create(self, backup_run, backup_entry_path, hash_hexdigest):
        backup_path = backup_run.path_part()
        rel_path = backup_entry_path.relative_to(backup_path)
        directory = rel_path.parent

        filename = backup_entry_path.name
        file_stat = backup_entry_path.stat()

        log.debug(
            "Save: %r %r %r %r %r",
            backup_run,
            directory,
            filename,
            hash_hexdigest,
            file_stat)
        directory, created = BackupDir.objects.get_or_create(directory=directory)
        filename, created = BackupFilename.objects.get_or_create(filename=filename)
        content_info, created = ContentInfo.objects.get_or_create(
            hash_hexdigest=hash_hexdigest, file_size=file_stat.st_size
        )

        backup_entry = super().create(
            backup_run=backup_run,
            directory=directory,
            filename=filename,
            content_info=content_info,
            file_mtime_ns=file_stat.st_mtime_ns,
        )
        path = backup_entry.get_backup_path()
        assert path.is_file(), f"File not exists: {path}"
        assert path.stat().st_mtime_ns == backup_entry.file_mtime_ns
        return backup_entry


class BackupEntry(models.Model):
    backup_run = models.ForeignKey(BackupRun, on_delete=models.CASCADE)
    directory = models.ForeignKey(BackupDir, on_delete=models.CASCADE)
    filename = models.ForeignKey(BackupFilename, on_delete=models.CASCADE)
    content_info = models.ForeignKey(ContentInfo, on_delete=models.CASCADE)
    file_mtime_ns = models.PositiveIntegerField(help_text=_(
        "Time of most recent content modification expressed in nanoseconds as an integer."))
    no_link_source = models.BooleanField(default=False, help_text=_(
        "Can this file be used as a hardlink source? (Will be set if a os.link() failed.)"))

    objects = BackupEntryManager()

    def get_backup_path(self):
        return Path2(
            self.backup_run.path_part(),
            self.directory.path_part(),
            self.filename.path_part())

    def __str__(self):
        return f"{self.get_backup_path()} {self.content_info} mtime:{self.file_mtime_ns}"

    class Meta:
        ordering = ["-backup_run__backup_datetime"]
        get_latest_by = "file_mtime_ns"
