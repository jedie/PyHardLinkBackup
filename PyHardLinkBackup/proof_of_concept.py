#!/usr/bin/python3

"""
    Python HardLink Backup
    ~~~~~~~~~~~~~~~~~~~~~~

    **WARNING: needs Python >=3.5 !

    :copyleft: 2015 by Jens Diemer
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""

import logging
import os
import sys
import time
import datetime
import hashlib

# time.clock() on windows and time.time() on linux
from timeit import default_timer

try:
    # https://github.com/tqdm/tqdm
    from tqdm import tqdm
except ImportError as err:
    raise ImportError("Please install 'tqdm': %s" % err)

# Use the built-in version of scandir/walk if possible, otherwise
# use the scandir module version
try:
    from os import scandir, walk # Python >=3.5
except ImportError:
    # use https://pypi.python.org/pypi/scandir
    try:
        from scandir import scandir, walk
    except ImportError:
        raise ImportError("For Python <2.5: Please install 'scandir' !")

from PyHardLinkBackup.human import human_time, human_filesize

log = logging.getLogger(__name__)

os.environ["DJANGO_SETTINGS_MODULE"] = "PyHardLinkBackup.django_project.settings"
import django
django.setup()

from PyHardLinkBackup.backup_app.models import BackupEntry, BackupRun


#~ DEFAULT_NEW_PATH_MODE=0o777
DEFAULT_NEW_PATH_MODE=0o700

BACKUP_SUB_FORMAT="%Y-%m-%d-%H%M%S"
CHUNK_SIZE = 64*1024

hash_constructor = hashlib.sha512
HAST_FILE_EXT = ".sha512"


SKIP_DIRS = (
    "__pycache__",
)
SKIP_FILE_EXT = (
    ".pyc",
    ".tmp", ".cache"
)


class PathHelper(object):
    """
    e.g.: backup run called with: /abs/source/path/source_root

    |<---------self.abs_src_filepath------------->|
    |                                             |
    |<--self.abs_src_root-->|<-self.sub_filepath->|
    |                          |                  |
    /abs/source/path/source_root/sub/path/filename
    |              | |         | |      | |      |
    +-------------'  +--------'  +-----'  +-----'
    |                |           |        |
    |                |           |        `-> self.filename
    |                |           `-> self.sub_path
    |                `-> self.backup_name (root dir to backup)
    `-> self.src_prefix_path

    |<---------self.abs_dst_filepath------------------>|
    |                                                  |
    |<----self.abs_dst_root----->|<-self.sub_filepath->|
    |                            |                     |
    |<---------self.abs_dst_path-+------->|        .---'
    |                            |        |        |
    /abs/destination/name/datetime/sub/path/filename
    |-------------'  |-'  |-----'  |-----'  |-----'
    |                |    |        |        `-> self.filename
    |                |    |        `-> self.sub_path
    |                |    `-> self.time_string (Start time of the backup run)
    |                `<- self.backup_name
    `- self.backup_root (root dir storage for all backups runs)
    """
    def __init__(self, backup_root):
        self.backup_root = self.abs_norm_path(backup_root)
        log.debug("backup_root: %r", self.backup_root)

        # set in self.set_src_path():
        self.abs_src_filepath = None
        self.abs_src_root = None
        self.src_prefix_path = None
        self.backup_name = None
        self.time_string = None
        self.abs_dst_root = None
        self.backup_run = None # BackupRun() django orm instance

        # set in set_src_filepath():
        self.abs_src_filepath = None
        self.sub_filepath = None
        self.sub_path = None
        self.filename = None
        self.abs_dst_path = None
        self.abs_dst_filepath = None
        self.abs_dst_hash_filepath = None

    def set_src_path(self, raw_path):
        """
        Set the source backup path.
        Called one time to start a backup run.
        """
        log.debug("set_src_path() with: %r", raw_path)

        self.abs_src_root = self.abs_norm_path(raw_path)
        log.debug(" * abs_src_root: %r", self.abs_src_root)

        if not os.path.isdir(self.abs_src_root):
            raise OSError("Source path %r doesn't exists!" % self.abs_src_root)

        self.src_prefix_path, self.backup_name = os.path.split(raw_path)
        log.debug(" * src_prefix_path: %r", self.src_prefix_path)
        log.debug(" * backup_name: %r", self.backup_name)

        backup_datetime = datetime.datetime.now()
        self.time_string = backup_datetime.strftime(BACKUP_SUB_FORMAT)
        log.debug(" * time_string: %r", self.time_string)

        self.abs_dst_root = os.path.join(self.backup_root, self.backup_name, self.time_string)
        log.debug(" * abs_dst_root: %r", self.abs_dst_root)

        self.backup_run = BackupRun.objects.create(
            self.backup_name,
            backup_datetime
        )
        log.debug(" * backup_run: %s" % self.backup_run)

    def set_src_filepath(self, src_filepath):
        """
        Set one filepath to backup this file.
        Called for every file in the source directory.
        """
        log.debug("set_src_filepath() with: %r", src_filepath)
        self.abs_src_filepath = self.abs_norm_path(src_filepath)
        log.debug(" * abs_src_filepath: %s" % self.abs_src_filepath)

        # FIXME:
        assert self.abs_src_filepath.startswith(self.abs_src_root)
        self.sub_filepath = self.abs_src_filepath[len(self.abs_src_root):]
        self.sub_filepath = self.sub_filepath.lstrip(os.sep)
        log.debug(" * sub_filepath: %s" % self.sub_filepath)

        self.sub_path, self.filename = os.path.split(self.sub_filepath)
        log.debug(" * sub_path: %s" % self.sub_path)
        log.debug(" * filename: %s" % self.filename)

        self.abs_dst_path = os.path.join(self.abs_dst_root, self.sub_path)
        log.debug(" * abs_dst_path: %s" % self.abs_dst_path)

        self.abs_dst_filepath = os.path.join(self.abs_dst_root, self.sub_filepath)
        log.debug(" * abs_dst_filepath: %s" % self.abs_dst_filepath)

        self.abs_dst_hash_filepath = self.abs_dst_filepath + HAST_FILE_EXT
        log.debug(" * abs_dst_hash_filepath: %s" % self.abs_dst_hash_filepath)

    def abs_norm_path(self, path):
        return os.path.normpath(os.path.abspath(path))


def walk2(top, followlinks=False):
    """
    Same as os.walk() except:
     - returns os.scandir() result (os.DirEntry() instance) and not entry.name
     - always topdown=True
    """
    dirs = []
    nondirs = []

    # We may not have read permission for top, in which case we can't
    # get a list of the files the directory contains.  os.walk
    # always suppressed the exception then, rather than blow up for a
    # minor reason when (say) a thousand readable directories are still
    # left to visit.  That logic is copied here.
    try:
        scandir_it = scandir(top)
    except OSError:
        return

    while True:
        try:
            try:
                entry = next(scandir_it)
            except StopIteration:
                break
        except OSError:
            return

        try:
            is_dir = entry.is_dir()
        except OSError:
            # If is_dir() raises an OSError, consider that the entry is not
            # a directory, same behaviour than os.path.isdir().
            is_dir = False

        if is_dir:
            if entry.name not in SKIP_DIRS:
                dirs.append(entry)
            else:
                log.debug("Skip directory: %r", entry.name)
        else:
            ext = os.path.splitext(entry.name)[1]
            if ext not in SKIP_FILE_EXT:
                nondirs.append(entry)
            else:
                log.debug("Skip file: %r", entry.name)

    yield top, dirs, nondirs

    # Recurse into sub-directories
    islink = os.path.islink
    for entry in dirs:
        # Issue #23605: os.path.islink() is used instead of caching
        # entry.is_symlink() result during the loop on os.scandir() because
        # the caller can replace the directory entry during the "yield"
        # above.
        if followlinks or not islink(entry.path):
            yield from walk2(entry.path, followlinks)


class FileBackup(object):
    def __init__(self, file_entry, backup_path):
        self.file_entry = file_entry # os.DirEntry() instance
        self.backup_path = backup_path # PathHelper(backup_root) instance

    def _deduplication_backup(self, file_entry, in_file, out_file, process_bar):
        hash = hash_constructor()
        while True:
            data = in_file.read(CHUNK_SIZE)
            if not data:
                break

            out_file.write(data)
            hash.update(data)
            process_bar.update(len(data))

        return hash

    def deduplication_backup(self, process_bar):
        new_bytes = 0
        stined_bytes = 0

        src_path = self.file_entry.path
        log.debug("*** deduplication backup: %r", src_path)

        self.backup_path.set_src_filepath(src_path)
        log.debug("abs_src_filepath:", self.backup_path.abs_src_filepath)
        log.debug("abs_dst_filepath:", self.backup_path.abs_dst_filepath)
        log.debug("abs_dst_hash_filepath:", self.backup_path.abs_dst_hash_filepath)
        log.debug("abs_dst_dir:", self.backup_path.abs_dst_path)

        if not os.path.isdir(self.backup_path.abs_dst_path):
            os.makedirs(self.backup_path.abs_dst_path, mode=DEFAULT_NEW_PATH_MODE)
        else:
            assert not os.path.isfile(self.backup_path.abs_dst_filepath), self.backup_path.abs_dst_filepath

        try:
            with open(self.backup_path.abs_src_filepath, "rb") as in_file:
                with open(self.backup_path.abs_dst_hash_filepath, "w") as hash_file:
                    with open(self.backup_path.abs_dst_filepath, "wb") as out_file:
                        hash = self._deduplication_backup(self.file_entry, in_file, out_file, process_bar)
                    hash_hexdigest = hash.hexdigest()
                    hash_file.write(hash_hexdigest)
        except KeyboardInterrupt:
            os.remove(self.backup_path.abs_dst_filepath)
            os.remove(self.backup_path.abs_dst_hash_filepath)
            sys.exit(-1)

        file_stat=self.file_entry.stat()
        file_size=file_stat.st_size

        old_backups = BackupEntry.objects.filter(
            content_info__hash_hexdigest=hash_hexdigest
        )
        no_old_backup = True
        for old_backup in old_backups:
            no_old_backup = False
            log.debug("+++ old:", old_backup)
            log.debug("+++ rel:", old_backup.get_backup_path())

            abs_old_backup_path = os.path.join(
                self.backup_path.backup_root,
                old_backup.get_backup_path()
            )
            log.debug("+++ abs:", abs_old_backup_path)
            if not os.path.isfile(abs_old_backup_path):
                log.debug("*** ERROR old file doesn't exist! %r", abs_old_backup_path)
                continue

            # TODO:
            # compare hash
            # compare current content
            os.remove(self.backup_path.abs_dst_filepath)
            os.link(abs_old_backup_path, self.backup_path.abs_dst_filepath)
            log.debug("Remove and link, ok.")
            log.info("Replaced with a hardlink to: %r" % abs_old_backup_path)
            new_bytes = 0
            stined_bytes = file_size
            break

        if no_old_backup:
            log.debug("+++ no old entry in database!")
            new_bytes = file_size
            stined_bytes = 0

        BackupEntry.objects.create(
            self.backup_path.backup_run,
            directory=self.backup_path.sub_path,
            filename=self.backup_path.filename,
            hash_hexdigest=hash_hexdigest,
            file_stat=file_stat,
        )

        # set origin access/modified times to the new created backup file
        atime_ns = file_stat.st_atime_ns
        mtime_ns = file_stat.st_mtime_ns
        os.utime(self.backup_path.abs_dst_filepath, ns=(atime_ns, mtime_ns))

        return new_bytes, stined_bytes


class HardLinkBackup(object):
    def __init__(self, backup_root):
        self.path = PathHelper(backup_root)

        os.makedirs(
            self.path.backup_root, mode=DEFAULT_NEW_PATH_MODE,
            exist_ok=True
        )
        if not os.path.isdir(self.path.backup_root):
            raise OSError(
                "Backup path %r doesn't exists!" % self.path.backup_root
            )

    def scandir(self, path):
        file_list = []
        total_size = 0
        start_time = default_timer()
        print("\nScan %r...\n" % path)
        for top, dirs, nondirs in tqdm(walk2(path), unit="dirs", leave=True):
            for entry in nondirs:
                if entry.is_file():
                    file_list.append(entry)
                    total_size += entry.stat().st_size
                else:
                    raise NotImplementedError("todo: %r", entry)

        print("\nscanned %i files in %s\n" % (
            len(file_list), human_time(default_timer()-start_time)
        ))
        return file_list, total_size

    def backup(self, src_path):
        self.path.set_src_path(src_path)

        file_list, total_size = self.scandir(self.path.abs_src_root)
        print("%i in %s files to backup." % (len(file_list), human_filesize(total_size)))

        total_new_bytes = 0
        total_stined_bytes = 0
        with tqdm(total=total_size, unit='B', unit_scale=True) as process_bar:
            for no, file_entry in enumerate(file_list):
                log.debug(no, file_entry.path)

                file_backup = FileBackup(file_entry, self.path)
                new_bytes, stined_bytes = file_backup.deduplication_backup(process_bar)
                total_new_bytes += new_bytes
                total_stined_bytes += stined_bytes

        return len(file_list), total_size, total_new_bytes, total_stined_bytes


if __name__ == '__main__':
    if sys.platform.startswith("win"):
        backup_root = "d:\PyHardLinkBackups"
    else:
        backup_root = os.path.expanduser("~/PyHardLinkBackups")

    start_time = default_timer()

    hardlinkbackup = HardLinkBackup(backup_root=backup_root)

    src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    # src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "django_project")

    file_count, total_size, total_new_bytes, total_stined_bytes = hardlinkbackup.backup(src_path=src_path)

    print("\nBackup done:")
    print(" * Files to backup: %i files" % file_count)
    print(" * Source file sizes: %s" % human_filesize(total_size))
    print(" * new bytes to saved: %s (%.1f%%)" % (
        human_filesize(total_new_bytes),
        (total_new_bytes/total_size*100)
    ))
    print(" * stint bytes via hardlinks: %s (%.1f%%)" % (
        human_filesize(total_stined_bytes),
        (total_stined_bytes/total_size*100)
    ))
    duration= default_timer() - start_time
    performance = total_size / duration / 1024.0 / 1024.0
    print(" * duration: %s %.1fMB/s\n" % (human_time(duration), performance))

