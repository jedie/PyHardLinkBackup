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
import traceback
from timeit import default_timer

import collections

from click._compat import strip_ansi

try:
    # https://github.com/tqdm/tqdm
    from tqdm import tqdm
except ImportError as err:
    raise ImportError("Please install 'tqdm': %s" % err)


log = logging.getLogger("phlb.%s" % __name__)


# os.environ["DJANGO_SETTINGS_MODULE"] = "PyHardLinkBackup.django_project.settings"
import django
from django.conf import settings

from PyHardLinkBackup.phlb.deduplicate import deduplicate
from PyHardLinkBackup.phlb.traceback_plus import exc_plus
from PyHardLinkBackup.phlb.filesystem_walk import scandir_walk, iter_filtered_dir_entry
from PyHardLinkBackup.phlb.pathlib2 import pprint_path
from PyHardLinkBackup.phlb.config import phlb_config
from PyHardLinkBackup.phlb.human import human_time, human_filesize, to_percent, ns2naturaltimesince, dt2naturaltimesince
from PyHardLinkBackup.backup_app.models import BackupEntry, BackupRun
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

    def __init__(self, dir_path, path_helper, backup_run):
        """
        :param dir_path: DirEntryPath() instance of the source file
        :param path_helper: PathHelper(backup_root) instance
        """
        self.dir_path = dir_path
        self.path_helper = path_helper
        self.backup_run = backup_run

        self.fast_backup = None # Was a fast backup used?
        self.file_linked = None # Was a hardlink used?

        if self._SIMULATE_SLOW_SPEED:
            log.error("Slow down speed for tests activated!")

    def _deduplication_backup(self, file_entry, in_file, out_file, process_bar):
        hash = hashlib.new(phlb_config.hash_name)
        while True:
            data = in_file.read(phlb_config.chunk_size)
            if not data:
                break

            if self._SIMULATE_SLOW_SPEED:
                log.error("Slow down speed for tests!")
                time.sleep(self._SIMULATE_SLOW_SPEED)

            out_file.write(data)
            hash.update(data)
            process_bar.update(len(data))
        return hash

    def fast_deduplication_backup(self, old_backup_entry, process_bar):
        """
        We can just link a old backup entry

        :param latest_backup: old BackupEntry model instance
        :param process_bar: tqdm process bar
        """
        # TODO: merge code with parts from deduplication_backup()
        src_path = self.dir_path.resolved_path
        log.debug("*** fast deduplication backup: '%s'", src_path)
        old_file_path = old_backup_entry.get_backup_path()

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

        with self.path_helper.abs_dst_hash_filepath.open("w") as hash_file:
            try:
                old_file_path.link(self.path_helper.abs_dst_filepath) # call os.link()
            except OSError as err:
                log.error("Can't link '%s' to '%s': %s" % (
                    old_file_path, self.path_helper.abs_dst_filepath, err
                ))
                log.info("Mark %r with 'no link source'.", old_backup_entry)
                old_backup_entry.no_link_source=True
                old_backup_entry.save()

                # do a normal copy backup
                self.deduplication_backup(process_bar)
                return

            hash_hexdigest = old_backup_entry.content_info.hash_hexdigest
            hash_file.write(hash_hexdigest)

        file_size = self.dir_path.stat.st_size
        if file_size>0:
            # tqdm will not accept 0 bytes files ;)
            process_bar.update(file_size)

        BackupEntry.objects.create(
            backup_run = self.backup_run,
            backup_entry_path = self.path_helper.abs_dst_filepath,
            hash_hexdigest=hash_hexdigest,
        )

        if self._SIMULATE_SLOW_SPEED:
            log.error("Slow down speed for tests!")
            time.sleep(self._SIMULATE_SLOW_SPEED)

        self.fast_backup = True # Was a fast backup used?
        self.file_linked = True # Was a hardlink used?

    def deduplication_backup(self, process_bar):
        """
        Backup the current file and compare the content.

        :param process_bar: tqdm process bar
        """
        self.fast_backup = False # Was a fast backup used?

        src_path = self.dir_path.resolved_path
        log.debug("*** deduplication backup: '%s'", src_path)

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
            # Try to remove created files
            try:
                self.path_helper.abs_dst_filepath.unlink()
            except OSError:
                pass
            try:
                self.path_helper.abs_dst_hash_filepath.unlink()
            except OSError:
                pass
            raise KeyboardInterrupt

        old_backup_entry = deduplicate(self.path_helper.abs_dst_filepath, hash_hexdigest)
        if old_backup_entry is None:
            log.debug("File is unique.")
            self.file_linked = False # Was a hardlink used?
        else:
            log.debug("File was deduplicated via hardlink to: %s" % old_backup_entry)
            self.file_linked = True # Was a hardlink used?

        # set origin access/modified times to the new created backup file
        atime_ns = self.dir_path.stat.st_atime_ns
        mtime_ns = self.dir_path.stat.st_mtime_ns
        self.path_helper.abs_dst_filepath.utime( # call os.utime()
            ns=(atime_ns, mtime_ns)
        )
        log.debug("Set mtime to: %s" % mtime_ns)

        BackupEntry.objects.create(
            backup_run = self.backup_run,
            backup_entry_path = self.path_helper.abs_dst_filepath,
            hash_hexdigest=hash_hexdigest,
        )

        self.fast_backup=False # Was a fast backup used?


class SkipPatternInformation:
    def __init__(self):
        self.data = collections.defaultdict(list)

    def __call__(self, entry, pattern):
        self.data[pattern].append(entry)

    def has_hits(self):
        if len(self.data) == 0:
            return False
        else:
            return True

    def short_info(self):
        lines = []
        for pattern, entries in sorted(self.data.items()):
            lines.append(" * %r match on %i items" % (pattern, len(entries)))
        return lines

    def long_info(self):
        lines = []
        for pattern, entries in sorted(self.data.items()):
            lines.append("%r match on:" % pattern)
            for entry in entries:
                lines.append(" * %s" % entry.path)
        return lines


class HardLinkBackup(object):
    def __init__(self, path_helper, summary):
        """
        :param src_path: Path2() instance of the source directory
        :param force_name: Force this name for the backup
        """
        self.start_time = default_timer()

        self.path_helper = path_helper
        self.summary = summary

        self.duration = 0
        self.total_file_link_count = 0
        self.total_stined_bytes = 0
        self.total_new_file_count = 0
        self.total_new_bytes = 0
        self.total_errored_items = 0
        self.total_fast_backup = 0

        old_backups = BackupRun.objects.filter(name=self.path_helper.backup_name)
        self.summary("%r was backuped %i time(s)" % (self.path_helper.backup_name, old_backups.count()))

        old_backups = old_backups.filter(completed=True)
        completed_count = old_backups.count()
        self.summary("There are %i backups finished completed." % completed_count)

        self.latest_backup = None
        self.latest_mtime_ns = None
        try:
            self.latest_backup = old_backups.latest()
        except BackupRun.DoesNotExist:
            self.summary("No old backup found with name %r" % self.path_helper.backup_name)
        else:
            latest_backup_datetime = self.latest_backup.backup_datetime
            self.summary("Latest backup from:", dt2naturaltimesince(latest_backup_datetime))

            backup_entries = BackupEntry.objects.filter(backup_run=self.latest_backup)
            try:
                latest_entry = backup_entries.latest()
            except BackupEntry.DoesNotExist:
                log.warn("Latest backup run contains no files?!?")
            else:
                self.latest_mtime_ns = latest_entry.file_mtime_ns
                self.summary("Latest backup entry modified time: %s" % ns2naturaltimesince(self.latest_mtime_ns))

        self.summary("Backup to: '%s'" % self.path_helper.abs_dst_root)
        self.path_helper.abs_dst_root.makedirs( # call os.makedirs()
            mode=phlb_config.default_new_path_mode,
            exist_ok=True
        )
        if not self.path_helper.abs_dst_root.is_dir():
            raise NotADirectoryError(
                "Backup path '%s' doesn't exists!" % self.path_helper.abs_dst_root
            )

        self.backup_run = BackupRun.objects.create(
            name = self.path_helper.backup_name,
            backup_datetime=self.path_helper.backup_datetime,
            completed = False,
        )
        log.debug(" * backup_run: %s" % self.backup_run)


    def backup(self):
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
            self._backup()
        finally:
            if copy_log:
                log.warn("copy log file from '%s' to '%s'" % (
                    settings.LOG_FILEPATH, self.path_helper.log_filepath
                ))
                temp_log_path.copyfile(self.path_helper.log_filepath) # call shutil.copyfile()

        self.backup_run.completed=True
        self.backup_run.save()

    def _evaluate_skip_pattern_info(self, skip_pattern_info, name):
        if not skip_pattern_info.has_hits():
            self.summary("%s doesn't match on any dir entry." % name)
        else:
            self.summary("%s match information:" % name)
            for line in skip_pattern_info.long_info():
                log.info(line)
            for line in skip_pattern_info.short_info():
                self.summary("%s\n" % line)

    def _scandir(self, path):
        start_time = default_timer()
        self.summary("\nScan '%s'...\n" % path)

        skip_pattern_info = SkipPatternInformation()

        skip_dirs = phlb_config.skip_dirs # TODO: add tests for it!
        self.summary("Scan filesystem with SKIP_DIRS: %s" % repr(skip_dirs))

        tqdm_iterator = tqdm(
            scandir_walk(path.path, skip_dirs, on_skip=skip_pattern_info),
            unit=" dir entries",
            leave=True
        )
        dir_entries = [entry for entry in tqdm_iterator]
        self.summary("\n * %i dir entries" % len(dir_entries))
        self._evaluate_skip_pattern_info(skip_pattern_info, name="SKIP_DIRS")

        self.total_size = 0
        self.file_count = 0
        filtered_dir_entries = []
        skip_patterns = phlb_config.skip_patterns # TODO: add tests for it!
        self.summary("Filter with SKIP_PATTERNS: %s" % repr(skip_patterns))
        skip_pattern_info = SkipPatternInformation()
        tqdm_iterator = tqdm(
            iter_filtered_dir_entry(dir_entries, skip_patterns, on_skip=skip_pattern_info),
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

        self.summary("\n * %i filtered dir entries" % len(filtered_dir_entries))
        self._evaluate_skip_pattern_info(skip_pattern_info, name="SKIP_PATTERNS")

        self.summary("\nscan/filter source directory in %s\n" % (
            human_time(default_timer()-start_time)
        ))
        return filtered_dir_entries

    def fast_compare(self, dir_path):
        """
        :param dir_path: filesystem_walk.DirEntryPath() instance
        """
        if self.latest_backup is None:
            # No old backup run was found
            return

        if self.latest_mtime_ns is None:
            # No timestamp from old backup run was found
            return

        # There was a completed old backup run
        # Check if we can made a 'fast compare'
        mtime_ns = dir_path.stat.st_mtime_ns
        if mtime_ns>self.latest_mtime_ns:
            # The current source file is newer than
            # the latest file from last completed backup
            log.info("Fast compare: source file is newer than latest backuped file.")
            return

        # Look into database and compare mtime and size

        try:
            old_backup_entry = BackupEntry.objects.get(
                backup_run=self.latest_backup,
                directory__directory=self.path_helper.sub_path,
                filename__filename=self.path_helper.filename,
                no_link_source=False,
            )
        except BackupEntry.DoesNotExist:
            log.debug("No old backup entry found")
            return

        content_info = old_backup_entry.content_info

        file_size = content_info.file_size
        if file_size != dir_path.stat.st_size:
            log.info("Fast compare: File size is different: %i != %i" % (file_size, dir_path.stat.st_size))
            return

        old_backup_filepath = old_backup_entry.get_backup_path()
        try:
            old_file_mtime_ns = old_backup_filepath.stat().st_mtime_ns
        except FileNotFoundError as err:
            log.error("Old backup file not found: %s" % err)
            old_backup_entry.no_link_source=True
            old_backup_entry.save()
            return

        if old_file_mtime_ns != old_backup_entry.file_mtime_ns:
            log.error("ERROR: mtime from database is different to the file!")
            log.error(" * File: %s" % old_backup_filepath)
            log.error(" * Database mtime: %s" % old_backup_entry.file_mtime_ns)
            log.error(" * File mtime: %s" % old_file_mtime_ns)

        if old_file_mtime_ns != dir_path.stat.st_mtime_ns:
            log.info("Fast compare mtime is different between:")
            log.info(" * %s" % old_backup_entry)
            log.info(" * %s" % dir_path)
            log.info(" * mtime: %i != %i" % (old_file_mtime_ns, dir_path.stat.st_mtime_ns))
            return

        # We found a old entry with same size and mtime
        return old_backup_entry

    def _backup_dir_item(self, dir_path, process_bar):
        """
        Backup one dir item

        :param dir_path: filesystem_walk.DirEntryPath() instance
        """
        self.path_helper.set_src_filepath(dir_path)
        if self.path_helper.abs_src_filepath is None:
            self.total_errored_items += 1
            log.info("Can't backup %r", dir_path)

        # self.summary(no, dir_path.stat.st_mtime, end=" ")
        if dir_path.is_symlink:
            self.summary("TODO Symlink: %s" % dir_path)
            return

        if dir_path.resolve_error is not None:
            self.summary("TODO resolve error: %s" % dir_path.resolve_error)
            pprint_path(dir_path)
            return

        if dir_path.different_path:
            self.summary("TODO different path:")
            pprint_path(dir_path)
            return

        if dir_path.is_dir:
            self.summary("TODO dir: %s" % dir_path)
        elif dir_path.is_file:
            # self.summary("Normal file: %s", dir_path)

            file_backup = FileBackup(dir_path, self.path_helper, self.backup_run)
            old_backup_entry = self.fast_compare(dir_path)
            if old_backup_entry is not None:
                # We can just link the file from a old backup
                file_backup.fast_deduplication_backup(old_backup_entry, process_bar)
            else:
                file_backup.deduplication_backup(process_bar)

            assert file_backup.fast_backup is not None, dir_path.path
            assert file_backup.file_linked is not None, dir_path.path

            file_size = dir_path.stat.st_size
            if file_backup.file_linked:
                # os.link() was used
                self.total_file_link_count += 1
                self.total_stined_bytes += file_size
            else:
                self.total_new_file_count += 1
                self.total_new_bytes += file_size

            if file_backup.fast_backup:
                self.total_fast_backup += 1
        else:
            self.summary("TODO:" % dir_path)
            pprint_path(dir_path)

    def _backup(self):
        dir_entries = self._scandir(self.path_helper.abs_src_root)

        msg="%s in %i files to backup." % (
            human_filesize(self.total_size), self.file_count,
        )
        self.summary(msg)
        log.info(msg)

        next_update_print = default_timer() + phlb_config.print_update_interval

        path_iterator = enumerate(sorted(
            dir_entries,
            key=lambda x: x.stat.st_mtime, # sort by last modify time
            reverse=True # sort from newest to oldes
        ))
        with tqdm(total=self.total_size, unit='B', unit_scale=True) as process_bar:
            for no, dir_path in path_iterator:
                try:
                    self._backup_dir_item(dir_path, process_bar)
                except BackupFileError as err:
                    # A known error with a good error message occurred,
                    # e.g: PermissionError to read source file.
                    log.error(err)
                    self.total_errored_items += 1
                except Exception as err:
                    # A unexpected error occurred.
                    # Print and add traceback to summary
                    log.error("Can't backup %s: %s" % (dir_path, err))
                    self.summary.handle_low_level_error()
                    self.total_errored_items += 1

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

        if self.total_errored_items:
            print(" * WARNING: %i omitted files!" % self.total_errored_items)

        print(" * fast backup: %i files" % self.total_fast_backup)

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
        if self.total_errored_items:
            summary.append(" * WARNING: %i omitted files!" % self.total_errored_items)

        summary.append(" * Source file sizes: %s" % human_filesize(self.total_size))
        summary.append(" * fast backup: %i files" % self.total_fast_backup)
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
        self.summary("\n%s\n" % "\n".join(self.get_summary()))


class SummaryFileHelper:
    def __init__(self, summary_file):
        self.summary_file = summary_file

    def __call__(self, *parts, sep=" ", end="\n", flush=False):
        print(*parts, sep=sep, end=end, flush=flush)
        self.summary_file.write(sep.join([strip_ansi(str(i)) for i in parts]))
        self.summary_file.write(end)
        if flush:
            self.summary_file.flush()

    def handle_low_level_error(self):
        self("_"*79)
        self("ERROR: Backup aborted with a unexpected error:")

        for line in exc_plus():
            self(line)

        self("-"*79)
        self("Please report this Bug here:")
        self("https://github.com/jedie/PyHardLinkBackup/issues/new", flush=True)
        self("-"*79)


def backup(path, name):
    django.setup()

    path_helper = PathHelper(path, name)

    # create backup destination to create summary file in there
    path_helper.summary_filepath.parent.makedirs( # calls os.makedirs()
        mode=phlb_config.default_new_path_mode,
        exist_ok=True
    )
    with path_helper.summary_filepath.open("w") as f:
        summary = SummaryFileHelper(f)

        summary("Start backup: %s" % path_helper.time_string)
        summary("Source path: %s" % path_helper.abs_src_root)

        phlb = HardLinkBackup(path_helper, summary)
        try:
            phlb.backup()
        except KeyboardInterrupt:
            summary(
                "Abort backup, because user hits the interrupt key during execution!",
                flush=True
            )
            # Calculate the correct omitted files count for print_summary()
            phlb.total_errored_items = phlb.file_count - (
                phlb.total_file_link_count + phlb.total_new_file_count
            )
        except Exception:
            summary.handle_low_level_error()
        finally:
            phlb.print_summary()
            summary("---END---", flush=True)


def print_skip_pattern_info(skip_pattern_info, name):
    if not skip_pattern_info.has_hits():
        print("%s doesn't match on any dir entry." % name)
    else:
        print("%s match information:" % name)
        for line in skip_pattern_info.long_info():
            log.info(line)
        for line in skip_pattern_info.short_info():
            print("%s\n" % line)


def scan_dir_tree(path, extra_skip_patterns=None):
    start_time = default_timer()
    print("\nScan '%s'...\n" % path)

    skip_pattern_info = SkipPatternInformation()

    skip_dirs = phlb_config.skip_dirs # TODO: add tests for it!
    print("Scan filesystem with SKIP_DIRS: %s" % repr(skip_dirs))

    tqdm_iterator = tqdm(
        scandir_walk(path.path, skip_dirs, on_skip=skip_pattern_info),
        unit=" dir entries",
        leave=True
    )
    dir_entries = [entry for entry in tqdm_iterator]
    print("\n * %i dir entries" % len(dir_entries))
    print_skip_pattern_info(skip_pattern_info, name="SKIP_DIRS")

    skip_patterns = phlb_config.skip_patterns # TODO: add tests for it!
    if extra_skip_patterns:
        skip_patterns = set(skip_patterns)
        for pattern in extra_skip_patterns:
            skip_patterns.add(pattern)
        skip_patterns = tuple(skip_patterns)
    print("Filter with SKIP_PATTERNS: %s" % repr(skip_patterns))

    skip_pattern_info = SkipPatternInformation()
    tqdm_iterator = tqdm(
        iter_filtered_dir_entry(dir_entries, skip_patterns, on_skip=skip_pattern_info),
        total=len(dir_entries),
        unit=" dir entries",
        leave=True
    )

    filtered_dir_entries = []
    for entry in tqdm_iterator:
        if entry is None:
            # filtered out by skip_patterns
            continue
        if entry.is_file:
            filtered_dir_entries.append(entry)
    tqdm_iterator.close()

    print("\n * %i filtered dir entries" % len(filtered_dir_entries))
    print_skip_pattern_info(skip_pattern_info, name="SKIP_PATTERNS")

    print("\nscan/filter source directory in %s" % (
        human_time(default_timer()-start_time)
    ))
    return filtered_dir_entries
