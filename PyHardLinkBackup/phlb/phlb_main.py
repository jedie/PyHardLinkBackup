#!/usr/bin/python3

"""
    Python HardLink Backup
    ~~~~~~~~~~~~~~~~~~~~~~

    :copyleft: 2015 by Jens Diemer
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""

import datetime
import logging
import sys

import hashlib
import os

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


log = logging.getLogger(__name__)


os.environ["DJANGO_SETTINGS_MODULE"] = "PyHardLinkBackup.django_project.settings"
import django
django.setup()


from PyHardLinkBackup.phlb import os_scandir
from PyHardLinkBackup.phlb.human import human_time, human_filesize
from PyHardLinkBackup.backup_app.models import BackupEntry, BackupRun, Config



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
    `- self.config.backup_path (root dir storage for all backups runs)
    """
    def __init__(self, src_path):
        self.abs_src_root = self.abs_norm_path(src_path)
        log.debug(" * abs_src_root: %r", self.abs_src_root)

        if not os.path.isdir(self.abs_src_root):
            raise OSError("Source path %r doesn't exists!" % self.abs_src_root)

        self.src_prefix_path, self.backup_name = os.path.split(self.abs_src_root)
        log.debug(" * src_prefix_path: %r", self.src_prefix_path)
        log.debug(" * backup_name: %r", self.backup_name)

        self.config, created=Config.objects.get_or_create(
            name=self.backup_name, note="Created by cli."
        )
        if created:
            print("New backup config created.")

        backup_datetime = datetime.datetime.now()
        self.time_string = backup_datetime.strftime(self.config.sub_dir_format)
        log.debug(" * time_string: %r", self.time_string)

        self.abs_dst_root = os.path.join(self.config.backup_path, self.backup_name, self.time_string)
        log.debug(" * abs_dst_root: %r", self.abs_dst_root)

        self.backup_run = BackupRun.objects.create(
            self.backup_name,
            backup_datetime
        )
        log.debug(" * backup_run: %s" % self.backup_run)

        # set in set_src_filepath():
        self.abs_src_filepath = None
        self.sub_filepath = None
        self.sub_path = None
        self.filename = None
        self.abs_dst_path = None
        self.abs_dst_filepath = None
        self.abs_dst_hash_filepath = None


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

        self.abs_dst_hash_filepath = self.abs_dst_filepath + os.extsep + self.config.hash_name
        log.debug(" * abs_dst_hash_filepath: %s" % self.abs_dst_hash_filepath)

    def abs_norm_path(self, path):
        return os.path.normpath(os.path.abspath(path))


class FileBackup(object):
    def __init__(self, file_entry, path_helper, config):
        self.file_entry = file_entry # os.DirEntry() instance
        self.path = path_helper # PathHelper(backup_root) instance
        self.config = config

    def _deduplication_backup(self, file_entry, in_file, out_file, process_bar):
        hash = hashlib.new(self.config.hash_name)
        while True:
            data = in_file.read(self.config.chunk_size)
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

        self.path.set_src_filepath(src_path)
        log.debug("abs_src_filepath:", self.path.abs_src_filepath)
        log.debug("abs_dst_filepath:", self.path.abs_dst_filepath)
        log.debug("abs_dst_hash_filepath:", self.path.abs_dst_hash_filepath)
        log.debug("abs_dst_dir:", self.path.abs_dst_path)

        if not os.path.isdir(self.path.abs_dst_path):
            default_mode=int(self.config.default_new_path_mode,8) # TODO: Move to model!
            os.makedirs(self.path.abs_dst_path, mode=default_mode)
        else:
            assert not os.path.isfile(self.path.abs_dst_filepath), self.path.abs_dst_filepath

        try:
            with open(self.path.abs_src_filepath, "rb") as in_file:
                with open(self.path.abs_dst_hash_filepath, "w") as hash_file:
                    with open(self.path.abs_dst_filepath, "wb") as out_file:
                        hash = self._deduplication_backup(self.file_entry, in_file, out_file, process_bar)
                    hash_hexdigest = hash.hexdigest()
                    hash_file.write(hash_hexdigest)
        except KeyboardInterrupt:
            os.remove(self.path.abs_dst_filepath)
            os.remove(self.path.abs_dst_hash_filepath)
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

            abs_old_backup_path = old_backup.get_backup_path()
            log.debug("+++ abs:", abs_old_backup_path)
            if not os.path.isfile(abs_old_backup_path):
                log.debug("*** ERROR old file doesn't exist! %r", abs_old_backup_path)
                continue

            # TODO:
            # compare hash
            # compare current content
            os.remove(self.path.abs_dst_filepath)
            os.link(abs_old_backup_path, self.path.abs_dst_filepath)
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
            self.path.backup_run,
            directory=self.path.sub_path,
            filename=self.path.filename,
            hash_hexdigest=hash_hexdigest,
            file_stat=file_stat,
        )

        # set origin access/modified times to the new created backup file
        atime_ns = file_stat.st_atime_ns
        mtime_ns = file_stat.st_mtime_ns
        os.utime(self.path.abs_dst_filepath, ns=(atime_ns, mtime_ns))

        return new_bytes, stined_bytes


class HardLinkBackup(object):
    def __init__(self, src_path):
        self.start_time = default_timer()
        self.path = PathHelper(src_path)

        self.config=self.path.config # models.Config() instance

        default_mode=int(self.config.default_new_path_mode,8) # TODO: Move to model!
        os.makedirs(
            self.path.abs_dst_root, mode=default_mode, exist_ok=True
        )
        if not os.path.isdir(self.path.abs_dst_root):
            raise OSError(
                "Backup path %r doesn't exists!" % self.path.abs_dst_root
            )

        self._backup()

    def _scandir(self, path):
        file_list = []
        total_size = 0
        start_time = default_timer()
        print("\nScan %r...\n" % path)

        skip_dirs = self.config.skip_dirs
        skip_files = self.config.skip_files
        print("Scan with skip dirs: %s" % repr(skip_dirs))
        print("Scan with skip files: %s" % repr(skip_files))
        fs_iterator = os_scandir.walk2(path, skip_dirs, skip_files)

        for top, dirs, nondirs in tqdm(fs_iterator, unit="dirs", leave=True):
            for entry in nondirs:
                if entry.is_file():
                    file_list.append(entry)
                    total_size += entry.stat().st_size
                else:
                    raise NotImplementedError("todo: %r", entry)

        self.file_count = len(file_list)
        self.total_size = total_size

        print("\nscanned %i files in %s\n" % (
            self.file_count, human_time(default_timer()-start_time)
        ))
        return file_list

    def _backup(self):
        file_list = self._scandir(self.path.abs_src_root)
        self.file_count = len(file_list)

        print("%s in %i files to backup." % (
            human_filesize(self.total_size), self.file_count,
        ))

        total_new_bytes = 0
        total_stined_bytes = 0
        with tqdm(total=self.total_size, unit='B', unit_scale=True) as process_bar:
            for no, file_entry in enumerate(file_list):
                log.debug(no, file_entry.path)

                file_backup = FileBackup(file_entry, self.path, self.config)
                new_bytes, stined_bytes = file_backup.deduplication_backup(process_bar)
                total_new_bytes += new_bytes
                total_stined_bytes += stined_bytes

        self.duration = default_timer() - self.start_time
        self.total_new_bytes = total_new_bytes
        self.total_stined_bytes = total_stined_bytes

    def get_summary(self):
        summary = ["Backup done:"]
        summary.append(" * Files to backup: %i files" % self.file_count)
        summary.append(" * Source file sizes: %s" % human_filesize(self.total_size))
        summary.append(" * new content to saved: %s (%.1f%%)" % (
            human_filesize(self.total_new_bytes),
            (self.total_new_bytes/self.total_size*100)
        ))
        summary.append(" * stint space via hardlinks: %s (%.1f%%)" % (
            human_filesize(self.total_stined_bytes),
            (self.total_stined_bytes/self.total_size*100)
        ))
        performance = self.total_size / self.duration / 1024.0 / 1024.0
        summary.append(" * duration: %s %.1fMB/s\n" % (human_time(self.duration), performance))
        return summary

    def print_summary(self):
        print("\n%s\n" % "\n".join(self.get_summary()))


if __name__ == '__main__':
    if not hasattr(sys, "real_prefix"):
        print("ERROR: virtualenv not activated!")
        sys.exit("-1")

    # src_path = sys.prefix
    src_path = os.path.join(sys.prefix, "src")
    # src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    # src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "django_project")

    print("\n*** Test run with: %r ***\n" % src_path)

    phlb = HardLinkBackup(src_path=src_path)
    phlb.print_summary()



