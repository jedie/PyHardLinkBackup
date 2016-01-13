#!/usr/bin/python3

"""
    Python HardLink Backup
    ~~~~~~~~~~~~~~~~~~~~~~

    :copyleft: 2015-2016 by Jens Diemer
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""

import datetime
import logging
import sys
import shutil
import hashlib
import os

# time.clock() on windows and time.time() on linux
from timeit import default_timer

try:
    # https://github.com/tqdm/tqdm
    from tqdm import tqdm
except ImportError as err:
    raise ImportError("Please install 'tqdm': %s" % err)


log = logging.getLogger("phlb.%s" % __name__)
#logging.basicConfig(level=logging.DEBUG)


# os.environ["DJANGO_SETTINGS_MODULE"] = "PyHardLinkBackup.django_project.settings"
import django


from PyHardLinkBackup.phlb import os_scandir
from PyHardLinkBackup.phlb.config import phlb_config
from PyHardLinkBackup.phlb.human import human_time, human_filesize
from PyHardLinkBackup.backup_app.models import BackupEntry, BackupRun


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
    `- phlb_config.backup_path (root dir storage for all backups runs)
    """
    def __init__(self, src_path):
        self.abs_src_root = self.abs_norm_path(src_path)
        log.debug(" * abs_src_root: '%s'", self.abs_src_root)

        if not os.path.isdir(self.abs_src_root):
            raise OSError("Source path '%s' doesn't exists!" % self.abs_src_root)

        self.src_prefix_path, self.backup_name = os.path.split(self.abs_src_root)
        log.debug(" * src_prefix_path: '%s'", self.src_prefix_path)
        log.debug(" * backup_name: '%s'", self.backup_name)

        backup_datetime = datetime.datetime.now()
        self.time_string = backup_datetime.strftime(phlb_config.sub_dir_formatter)
        log.debug(" * time_string: %r", self.time_string)

        self.abs_dst_root = os.path.join(phlb_config.backup_path, self.backup_name, self.time_string)
        log.debug(" * abs_dst_root: '%s'", self.abs_dst_root)

        self.backup_run = BackupRun.objects.create(
            name = self.backup_name,
            backup_datetime=backup_datetime
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
        log.debug("set_src_filepath() with: '%s'", src_filepath)
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

        self.abs_dst_hash_filepath = self.abs_dst_filepath + os.extsep + phlb_config.hash_name
        log.debug(" * abs_dst_hash_filepath: %s" % self.abs_dst_hash_filepath)

    def abs_norm_path(self, path):
        return os.path.normpath(os.path.abspath(os.path.expanduser(path)))


class FileBackup(object):
    def __init__(self, file_entry, path_helper):
        self.file_entry = file_entry # os.DirEntry() instance
        self.path = path_helper # PathHelper(backup_root) instance

    def _deduplication_backup(self, file_entry, in_file, out_file, process_bar):
        hash = hashlib.new(phlb_config.hash_name)
        while True:
            data = in_file.read(phlb_config.chunk_size)
            if not data:
                break

            out_file.write(data)
            hash.update(data)
            process_bar.update(len(data))
        return hash

    def deduplication_backup(self, process_bar):
        src_path = self.file_entry.path
        log.debug("*** deduplication backup: '%s'", src_path)

        self.path.set_src_filepath(src_path)
        log.debug("abs_src_filepath: '%s'", self.path.abs_src_filepath)
        log.debug("abs_dst_filepath: '%s'", self.path.abs_dst_filepath)
        log.debug("abs_dst_hash_filepath: '%s'", self.path.abs_dst_hash_filepath)
        log.debug("abs_dst_dir: '%s'", self.path.abs_dst_path)

        if not os.path.isdir(self.path.abs_dst_path):
            os.makedirs(
                self.path.abs_dst_path,
                mode=phlb_config.default_new_path_mode
            )
        else:
            assert not os.path.isfile(self.path.abs_dst_filepath), "Out file already exists: %r" % self.path.abs_src_filepath

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

        old_backups = BackupEntry.objects.filter(
            content_info__hash_hexdigest=hash_hexdigest
        )
        file_linked = False
        for old_backup in old_backups:
            log.debug("+++ old: '%s'", old_backup)
            abs_old_backup_path = old_backup.get_backup_path()
            if not os.path.isfile(abs_old_backup_path):
                log.error("*** ERROR old file doesn't exist! '%s'", abs_old_backup_path)
                continue

            # TODO:
            # compare hash
            # compare current content
            os.remove(self.path.abs_dst_filepath)

            assert abs_old_backup_path != self.path.abs_dst_filepath
            os.link(abs_old_backup_path, self.path.abs_dst_filepath)

            file_linked = True
            log.info("Replaced with a hardlink to: '%s'" % abs_old_backup_path)
            break

        file_stat=self.file_entry.stat()

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

        return file_linked, file_stat.st_size


class HardLinkBackup(object):
    def __init__(self, src_path):
        self.start_time = default_timer()
        self.path = PathHelper(src_path)

        print("Backup to: '%s'" % self.path.abs_dst_root)
        os.makedirs(
            self.path.abs_dst_root,
            mode=phlb_config.default_new_path_mode,
            exist_ok=True
        )
        if not os.path.isdir(self.path.abs_dst_root):
            raise OSError(
                "Backup path '%s' doesn't exists!" % self.path.abs_dst_root
            )

        try:
            self._backup()
        except KeyboardInterrupt:
            print("\nCleanup after keyboard interrupt:")

            print("\t* clean '%s'" % self.path.abs_dst_root)
            def print_error(fn, path, excinfo):
                print("\tError remove: '%s'" % path)
            shutil.rmtree(self.path.abs_dst_root, ignore_errors=True, onerror=print_error)

            # TODO: Remove unused ForeignKey, too,
            queryset = BackupEntry.objects.filter(backup_run=self.path.backup_run)
            count = queryset.count()
            print("\t* cleanup %i database entries" % count)
            queryset.delete()

            print("Bye")
            sys.exit(1)

    def _scandir(self, path):
        file_list = []
        total_size = 0
        start_time = default_timer()
        print("\nScan '%s'...\n" % path)

        skip_dirs = phlb_config.skip_dirs
        skip_files = phlb_config.skip_files
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

        self.total_file_link_count = 0
        self.total_stined_bytes = 0
        self.total_new_file_count = 0
        self.total_new_bytes = 0
        with tqdm(total=self.total_size, unit='B', unit_scale=True) as process_bar:
            for no, file_entry in enumerate(file_list):
                log.debug("%i '%s'", no, file_entry.path)

                file_backup = FileBackup(file_entry, self.path)
                file_linked, file_size = file_backup.deduplication_backup(process_bar)
                if file_linked:
                    # os.link() was used
                    self.total_file_link_count += 1
                    self.total_stined_bytes += file_size
                else:
                    self.total_new_file_count += 1
                    self.total_new_bytes += file_size

        self.duration = default_timer() - self.start_time

    def get_summary(self):
        summary = ["Backup done:"]
        summary.append(" * Files to backup: %i files" % self.file_count)
        summary.append(" * Source file sizes: %s" % human_filesize(self.total_size))
        summary.append(" * new content to saved: %i files (%s %.1f%%)" % (
            self.total_new_file_count,
            human_filesize(self.total_new_bytes),
            (self.total_new_bytes/self.total_size*100)
        ))
        summary.append(" * stint space via hardlinks: %i files (%s %.1f%%)" % (
            self.total_file_link_count,
            human_filesize(self.total_stined_bytes),
            (self.total_stined_bytes/self.total_size*100)
        ))
        performance = self.total_size / self.duration / 1024.0 / 1024.0
        summary.append(" * duration: %s %.1fMB/s\n" % (human_time(self.duration), performance))
        return summary

    def print_summary(self):
        print("\n%s\n" % "\n".join(self.get_summary()))


def backup(path):
    django.setup()
    phlb = HardLinkBackup(src_path=path)
    phlb.print_summary()

if __name__ == '__main__':
    src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    # src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "django_project")

    print("\n*** Test run with: '%s' ***\n" % src_path)

    phlb = HardLinkBackup(src_path=src_path)
    phlb.print_summary()



