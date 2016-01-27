#!/usr/bin/python3

"""
    Python HardLink Backup
    ~~~~~~~~~~~~~~~~~~~~~~

    :copyleft: 2015-2016 by Jens Diemer
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""
import datetime
import hashlib
import logging
import sys
import time

# time.clock() on windows and time.time() on linux
from timeit import default_timer

from django.conf import settings

try:
    # https://github.com/tqdm/tqdm
    from tqdm import tqdm
except ImportError as err:
    raise ImportError("Please install 'tqdm': %s" % err)


log = logging.getLogger("phlb.%s" % __name__)


# os.environ["DJANGO_SETTINGS_MODULE"] = "PyHardLinkBackup.django_project.settings"
import django


from PyHardLinkBackup.phlb.filesystem_walk import scandir_walk, iter_filtered_dir_entry, \
    pprint_path
from PyHardLinkBackup.phlb.config import phlb_config
from PyHardLinkBackup.phlb.human import human_time, human_filesize, to_percent
from PyHardLinkBackup.backup_app.models import BackupEntry
from PyHardLinkBackup.phlb.path_helper import PathHelper
from PyHardLinkBackup.phlb.pathlib2 import Path2


class BackupFileError(Exception):
    pass


class FileBackup(object):
    """
    backup one file
    """
    # TODO: remove with Mock solution:
    _SIMULATE_SLOW_SPEED=False # for unittests only!

    def __init__(self, dir_path, path_helper):
        """
        :param dir_path: DirEntryPath() instance of the source file
        :param path_helper: PathHelper(backup_root) instance
        """
        self.dir_path = dir_path
        self.path_helper = path_helper

    def _deduplication_backup(self, file_entry, in_file, out_file, process_bar):
        hash = hashlib.new(phlb_config.hash_name)
        while True:
            data = in_file.read(phlb_config.chunk_size)
            if not data:
                break

            if self._SIMULATE_SLOW_SPEED:
                log.error("Slow down speed for unittest!")
                time.sleep(self._SIMULATE_SLOW_SPEED)

            out_file.write(data)
            hash.update(data)
            process_bar.update(len(data))
        return hash

    def deduplication_backup(self, process_bar):
        src_path = self.dir_path.resolved_path
        log.debug("*** deduplication backup: '%s'", src_path)

        self.path_helper.set_src_filepath(self.dir_path)
        log.debug("abs_src_filepath: '%s'", self.path_helper.abs_src_filepath)
        log.debug("abs_dst_filepath: '%s'", self.path_helper.abs_dst_filepath)
        log.debug("abs_dst_hash_filepath: '%s'", self.path_helper.abs_dst_hash_filepath)
        log.debug("abs_dst_dir: '%s'", self.path_helper.abs_dst_path)

        if not self.path_helper.abs_dst_path.is_dir():
            try:
                self.path_helper.abs_dst_path.makedirs(
                    mode=phlb_config.default_new_path_mode
                )
            except OSError as err:
                raise BackupFileError(
                    "Error creating out path: %s" % err
                )
        else:
            assert not self.path_helper.abs_dst_filepath.is_file(), "Out file already exists: %r" % self.path_helper.abs_src_filepath

        try:
            try:
                with self.path_helper.abs_src_filepath.open("rb") as in_file:
                    with self.path_helper.abs_dst_hash_filepath.open("w") as hash_file:
                        with self.path_helper.abs_dst_filepath.open("wb") as out_file:
                            hash = self._deduplication_backup(self.dir_path, in_file, out_file, process_bar)
                        hash_hexdigest = hash.hexdigest()
                        hash_file.write(hash_hexdigest)
            except OSError as err:
                # FIXME: Better error message
                raise BackupFileError(
                    "Skip file %s error: %s" % (self.path_helper.abs_src_filepath, err)
                )
        except KeyboardInterrupt:
            self.path_helper.abs_dst_filepath.unlink()
            self.path_helper.abs_dst_hash_filepath.unlink()
            sys.exit(-1)

        temp_bak_name=Path2(
            "%s.bak" % self.path_helper.abs_dst_filepath # FIXME
        )

        old_backups = BackupEntry.objects.filter(
            content_info__hash_hexdigest=hash_hexdigest,
            no_link_source=False,
        )
        file_linked = False
        for old_backup in old_backups:
            log.debug("+++ old: '%s'", old_backup)
            abs_old_backup_path = old_backup.get_backup_path()
            if not abs_old_backup_path.is_file():
                log.error("*** ERROR old file doesn't exist! '%s'", abs_old_backup_path)
                continue

            assert abs_old_backup_path != self.path_helper.abs_dst_filepath

            # TODO: compare hash / current content before replace with a link

            # FIXME
            self.path_helper.abs_dst_filepath.rename(temp_bak_name)
            try:
                abs_old_backup_path.link(self.path_helper.abs_dst_filepath) # call os.link()
            except OSError as err:
                temp_bak_name.rename(self.path_helper.abs_dst_filepath)
                log.error("Can't link '%s' to '%s': %s" % (
                    abs_old_backup_path, self.path_helper.abs_dst_filepath, err
                ))
                log.info("Mark %r with 'no link source'.", old_backup)
                old_backup.no_link_source=True
                old_backup.save()
            else:
                temp_bak_name.unlink() # FIXME
                file_linked = True
                log.info("Replaced with a hardlink to: '%s'" % abs_old_backup_path)
                break

        BackupEntry.objects.create(
            self.path_helper.backup_run,
            directory=self.path_helper.sub_path,
            filename=self.path_helper.filename,
            hash_hexdigest=hash_hexdigest,
            file_stat=self.dir_path.stat,
        )

        # set origin access/modified times to the new created backup file
        atime_ns = self.dir_path.stat.st_atime_ns
        mtime_ns = self.dir_path.stat.st_mtime_ns
        self.path_helper.abs_dst_filepath.utime( # call os.utime()
            ns=(atime_ns, mtime_ns)
        )

        return file_linked, self.dir_path.stat.st_size


class HardLinkBackup(object):
    def __init__(self, src_path, force_name=None):
        """
        :param src_path: Path2() instance of the source directory
        :param force_name: Force this name for the backup
        """
        self.start_time = default_timer()
        self.duration = 0
        self.path_helper = PathHelper(src_path, force_name)

        print("Backup to: '%s'" % self.path_helper.abs_dst_root)
        self.path_helper.abs_dst_root.makedirs( # call os.makedirs()
            mode=phlb_config.default_new_path_mode,
            exist_ok=True
        )
        if not self.path_helper.abs_dst_root.is_dir():
            raise OSError(
                "Backup path '%s' doesn't exists!" % self.path_helper.abs_dst_root
            )

        # make temp file available in destination via link ;)
        temp_log_path = Path2(settings.LOG_FILEPATH)
        assert temp_log_path.is_file(), "%s doesn't exists?!?" % settings.LOG_FILEPATH
        try:
            temp_log_path.link(self.path_helper.log_filepath) # call os.link()
        except OSError as err:
            # e.g.:
            # temp is on a other drive than the destination
            log.error("Can't link log file: %s" % err)
            copy_log=True
        else:
            copy_log=False

        try:
            with self.path_helper.summary_filepath.open("w") as summary_file:
                summary_file.write("Start backup: %s\n\n" % self.path_helper.time_string)
                summary_file.write("Source: %s\n\n" % self.path_helper.abs_src_root)

                self._backup()

                summary_file.write("\n".join(self.get_summary()))
        finally:
            if copy_log:
                log.warn("copy log file from '%s' to '%s'" % (
                    settings.LOG_FILEPATH, self.path_helper.log_filepath
                ))
                temp_log_path.copyfile(self.path_helper.log_filepath) # call shutil.copyfile()

    def _scandir(self, path):
        start_time = default_timer()
        print("\nScan '%s'...\n" % path)

        def on_skip(entry, pattern):
            log.error("Skip pattern %r hit: %s" % (pattern, entry.path))

        skip_dirs = phlb_config.skip_dirs
        print("Scan filesystem with skip dirs: %s" % repr(skip_dirs))

        tqdm_iterator = tqdm(
            scandir_walk(path.path, skip_dirs, on_skip=on_skip),
            unit=" dir entries",
            leave=True
        )
        dir_entries = [entry for entry in tqdm_iterator]
        print("\n * %i dir entries" % len(dir_entries))

        self.total_size = 0
        self.file_count = 0
        filtered_dir_entries = []
        skip_patterns = phlb_config.skip_patterns
        print("Filter with skip patterns: %s" % repr(skip_patterns))
        tqdm_iterator = tqdm(
            iter_filtered_dir_entry(dir_entries, skip_patterns, on_skip),
            total=len(dir_entries),
            unit=" dir entries",
            leave=True
        )
        for entry in tqdm_iterator:
            if entry is None:
                # filtered out by skip_patterns
                continue
            if entry.is_file:
                filtered_dir_entries.append(entry)
                self.file_count += 1
                self.total_size += entry.stat.st_size

        print("\n * %i filtered dir entries" % len(filtered_dir_entries))

        print("\nscan/filter source directory in %s\n" % (
            human_time(default_timer()-start_time)
        ))
        return filtered_dir_entries

    def _backup(self):
        dir_entries = self._scandir(self.path_helper.abs_src_root)

        msg="%s in %i files to backup." % (
            human_filesize(self.total_size), self.file_count,
        )
        print(msg)
        log.info(msg)

        self.total_file_link_count = 0
        self.total_stined_bytes = 0
        self.total_new_file_count = 0
        self.total_new_bytes = 0
        self.total_skip_patterns = 0
        next_update_print = default_timer() + phlb_config.print_update_interval

        path_iterator = enumerate(sorted(
            dir_entries,
            key=lambda x: x.stat.st_mtime, # sort by last modify time
            reverse=True # sort from newest to oldes
        ))
        with tqdm(total=self.total_size, unit='B', unit_scale=True) as process_bar:
            for no, dir_path in path_iterator:
                # dir_path is a filesystem_walk.DirEntryPath() instance

                log.debug("%i %s", no, dir_path)
                # print("%i %s" % (no, dir_path))

                # print(no, dir_path.stat.st_mtime, end=" ")
                if dir_path.is_symlink:
                    print("TODO Symlink: %s" % dir_path)
                    continue

                if dir_path.different_path or dir_path.resolve_error:
                    print("TODO different path:")
                    pprint_path(dir_path)
                    continue

                if dir_path.is_dir:
                    print("TODO dir: %s" % dir_path)
                elif dir_path.is_file:
                    # print("Normal file: %s", dir_path)
                    file_backup = FileBackup(dir_path, self.path_helper)
                    try:
                        file_linked, file_size = file_backup.deduplication_backup(process_bar)
                    except BackupFileError as err:
                        log.error(err)
                        self.total_skip_patterns += 1
                    else:
                        if file_linked:
                            # os.link() was used
                            self.total_file_link_count += 1
                            self.total_stined_bytes += file_size
                        else:
                            self.total_new_file_count += 1
                            self.total_new_bytes += file_size
                else:
                    print("TODO:" % dir_path)
                    pprint_path(dir_path)

                if default_timer()>next_update_print:
                    self.print_update()
                    next_update_print = default_timer() + phlb_config.print_update_interval

        self.duration = default_timer() - self.start_time

    def print_update(self):
        """
        print some status information in between.
        """
        print("\r\n")
        now = datetime.datetime.now()
        print("Update info: (from: %s)" % now.strftime("%c"))

        current_total_size = self.total_stined_bytes + self.total_new_bytes

        if self.total_skip_patterns:
            print(" * WARNING: Skipped %i files!" % self.total_skip_patterns)

        print(" * new content saved: %i files (%s %.1f%%)" % (
            self.total_new_file_count,
            human_filesize(self.total_new_bytes),
            to_percent(self.total_new_bytes, current_total_size)
        ))

        print(" * stint space via hardlinks: %i files (%s %.1f%%)" % (
            self.total_file_link_count,
            human_filesize(self.total_stined_bytes),
            to_percent(self.total_stined_bytes, current_total_size)
        ))

        duration = default_timer() - self.start_time
        performance = current_total_size / duration / 1024.0 / 1024.0
        print(" * present performance: %.1fMB/s\n" % performance)

    def get_summary(self):
        summary = ["Backup done:"]
        summary.append(" * Files to backup: %i files" % self.file_count)
        if self.total_skip_patterns:
            summary.append(" * WARNING: Skipped %i files!" % self.total_skip_patterns)
        summary.append(" * Source file sizes: %s" % human_filesize(self.total_size))
        summary.append(" * new content saved: %i files (%s %.1f%%)" % (
            self.total_new_file_count,
            human_filesize(self.total_new_bytes),
            to_percent(self.total_new_bytes, self.total_size)
        ))
        summary.append(" * stint space via hardlinks: %i files (%s %.1f%%)" % (
            self.total_file_link_count,
            human_filesize(self.total_stined_bytes),
            to_percent(self.total_stined_bytes, self.total_size)
        ))
        if self.duration:
            performance = self.total_size / self.duration / 1024.0 / 1024.0
        else:
            performance = 0
        summary.append(" * duration: %s %.1fMB/s\n" % (human_time(self.duration), performance))
        return summary

    def print_summary(self):
        print("\n%s\n" % "\n".join(self.get_summary()))


def backup(path, name):
    django.setup()
    phlb = HardLinkBackup(src_path=path, force_name=name)
    phlb.print_summary()





