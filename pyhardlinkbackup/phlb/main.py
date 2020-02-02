"""
    Python HardLink Backup
    ~~~~~~~~~~~~~~~~~~~~~~

    :copyleft: 2015-2019 by Jens Diemer
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import logging

# https://github.com/jedie/pathlib_revised/
from pathlib_revised import DirEntryPath
from pathlib_revised.pathlib import pprint_path

# https://github.com/jedie/IterFilesystem
from iterfilesystem.humanize import human_filesize, human_time
from iterfilesystem.iter_scandir import ScandirWalker
from iterfilesystem.main import IterFilesystem

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.backup_app.models import BackupEntry, BackupRun
from pyhardlinkbackup.phlb.backup import FileBackup
from pyhardlinkbackup.phlb.config import phlb_config
from pyhardlinkbackup.phlb.humanize import dt2naturaltimesince, ns2naturaltimesince, to_percent
from pyhardlinkbackup.phlb.path_helper import PathHelper
from pyhardlinkbackup.phlb.summary_file import SummaryFileHelper

log = logging.getLogger(f"phlb.{__name__}")


class BackupIterFilesystem(IterFilesystem):
    def __init__(self, *, backup_path, backup_name, **kwargs):
        super().__init__(**kwargs)

        self.backup_path = backup_path
        self.backup_name = backup_name

    def start(self):
        self.path_helper = PathHelper(src_path=self.backup_path, force_name=self.backup_name)

        # create backup destination to create summary file in there
        self.path_helper.summary_filepath.parent.makedirs(  # calls os.makedirs()
            mode=phlb_config.default_new_path_mode, exist_ok=True
        )

        self.summary_file = self.path_helper.summary_filepath.open("w")
        self.summary = SummaryFileHelper(self.summary_file)

        old_backups = BackupRun.objects.filter(name=self.path_helper.backup_name)
        self.summary(f"{self.path_helper.backup_name!r} was backuped {old_backups.count():d} time(s)")

        old_backups = old_backups.filter(completed=True)
        completed_count = old_backups.count()
        self.summary(f"There are {completed_count:d} backups finished completed.")

        self.latest_backup = None
        self.latest_mtime_ns = None
        try:
            self.latest_backup = old_backups.latest()
        except BackupRun.DoesNotExist:
            self.summary(f"No old backup found with name {self.path_helper.backup_name!r}")
        else:
            latest_backup_datetime = self.latest_backup.backup_datetime
            self.summary("Latest backup from:", dt2naturaltimesince(latest_backup_datetime))

            backup_entries = BackupEntry.objects.filter(backup_run=self.latest_backup)
            try:
                latest_entry = backup_entries.latest()
            except BackupEntry.DoesNotExist:
                log.warning("Latest backup run contains no files?!?")
            else:
                self.latest_mtime_ns = latest_entry.file_mtime_ns
                self.summary(
                    "Latest backup entry modified time: %s" %
                    ns2naturaltimesince(
                        self.latest_mtime_ns))

        self.summary(f"Backup to: '{self.path_helper.abs_dst_root}'")
        self.path_helper.abs_dst_root.makedirs(  # call os.makedirs()
            mode=phlb_config.default_new_path_mode, exist_ok=True
        )
        if not self.path_helper.abs_dst_root.is_dir():
            raise NotADirectoryError(
                f"Backup path '{self.path_helper.abs_dst_root}' doesn't exists!")

        self.backup_run = BackupRun.objects.create(
            name=self.path_helper.backup_name,
            backup_datetime=self.path_helper.backup_datetime,
            completed=False)
        log.debug(f" * backup_run: {self.backup_run}")

        self.summary(f"Start backup: {self.path_helper.time_string}")
        self.summary(f"Source path: {self.path_helper.abs_src_root}")

        # init own attributes in Statistics() instance:
        self.stats_helper.total_file_link_count = 0
        self.stats_helper.total_stined_bytes = 0
        self.stats_helper.total_new_file_count = 0
        self.stats_helper.total_new_bytes = 0
        self.stats_helper.total_fast_backup = 0

        super().start()

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
        if mtime_ns > self.latest_mtime_ns:
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
            log.info(
                f"Fast compare: File size is different: {file_size:d} != {dir_path.stat.st_size:d}")
            return

        old_backup_filepath = old_backup_entry.get_backup_path()
        try:
            old_file_mtime_ns = old_backup_filepath.stat().st_mtime_ns
        except FileNotFoundError as err:
            log.error(f"Old backup file not found: {err}")
            old_backup_entry.no_link_source = True
            old_backup_entry.save()
            return

        if old_file_mtime_ns != old_backup_entry.file_mtime_ns:
            return
            log.error("ERROR: mtime from database is different to the file!")
            log.error(f" * File: {old_backup_filepath}")
            log.error(f" * Database mtime: {old_backup_entry.file_mtime_ns}")
            log.error(f" * File mtime: {old_file_mtime_ns}")

        if old_file_mtime_ns != dir_path.stat.st_mtime_ns:
            log.info("Fast compare mtime is different between:")
            log.info(f" * {old_backup_entry}")
            log.info(f" * {dir_path}")
            log.info(f" * mtime: {old_file_mtime_ns:d} != {dir_path.stat.st_mtime_ns:d}")
            return

        # We found a old entry with same size and mtime
        return old_backup_entry

    def process_dir_entry(self, dir_entry, process_bars):
        """
        Backup one dir item
        """
        dir_path = DirEntryPath(dir_entry)

        if dir_path.is_symlink:
            # self.summary("TODO Symlink: %s" % dir_path)
            return

        if dir_path.resolve_error is not None:
            self.summary(f"TODO resolve error: {dir_path.resolve_error}")
            pprint_path(dir_path)
            return

        if dir_path.different_path:
            self.summary("TODO different path:")
            pprint_path(dir_path)
            return

        if dir_path.is_dir:
            # self.summary("TODO dir: %s" % dir_path)
            return

        if dir_path.is_file:
            # self.summary("Normal file: %s", dir_path)

            # self.file_count += 1
            # self.total_size += dir_path.stat.st_size

            self.path_helper.set_src_filepath(dir_path)
            if self.path_helper.abs_src_filepath is None:
                self.stats_helper.total_errored_items += 1
                log.info("Can't backup %r", dir_path)
                return

            file_backup = FileBackup(
                dir_path=dir_path,
                worker=self,
                process_bars=process_bars
            )
            old_backup_entry = self.fast_compare(dir_path)
            if old_backup_entry is not None:
                # We can just link the file from a old backup
                file_backup.fast_deduplication_backup(old_backup_entry)
            else:
                file_backup.deduplication_backup()

            assert file_backup.fast_backup is not None, dir_path.path
            assert file_backup.file_linked is not None, dir_path.path

            file_size = dir_path.stat.st_size
            if file_backup.file_linked:
                # os.link() was used
                self.stats_helper.total_file_link_count += 1
                self.stats_helper.total_stined_bytes += file_size
            else:
                self.stats_helper.total_new_file_count += 1
                self.stats_helper.total_new_bytes += file_size

            if file_backup.fast_backup:
                self.stats_helper.total_fast_backup += 1
        else:
            self.summary("TODO:" % dir_path)
            pprint_path(dir_path)

    def get_summary(self):
        stats = self.stats_helper
        duration = stats.process_duration
        human_duration = human_time(duration)

        process_file_size = stats.process_file_size

        summary = [
            (
                f'Backup done in {human_duration}'
                f' ({stats.collect_dir_item_count} filesystem items)'
            ),
            f' * {stats.walker_dir_skip_count} directories skipped.',
            f' * {stats.walker_file_skip_count} files skipped.',
            f' * Files to backup: {stats.process_files} files',
        ]

        if stats.process_error_count:
            summary.append(f' * WARNING: {stats.process_error_count} omitted files!')

        performance = process_file_size / duration / 1024.0 / 1024.0
        summary += [
            f' * Source file sizes: {human_filesize(stats.collect_file_size)}',
            f' * fast backup: {stats.total_fast_backup} files',
            (f' * new content saved: {stats.total_new_file_count} files'
             f' ({human_filesize(stats.total_new_bytes)}'
             f' {to_percent(stats.total_new_bytes, process_file_size):.1f}%)'),
            (f' * stint space via hardlinks: {stats.total_file_link_count} files'
             f' ({human_filesize(stats.total_stined_bytes)}'
             f' {to_percent(stats.total_stined_bytes,process_file_size):.1f}%)'),
            f' * duration: {human_duration} {performance:.1f}MB/s',
        ]
        return summary

    def print_summary(self):
        self.summary("\n%s\n" % "\n".join(self.get_summary()))

    def done(self):
        self.summary(f'stats={self.stats_helper.pformat()}', verbose=False)
        self.print_summary()
        self.summary_file.close()


def backup(path, name, wait=False):
    path_helper = PathHelper(path, name)

    backup_worker = BackupIterFilesystem(
        ScanDirClass=ScandirWalker,
        scan_dir_kwargs=dict(
            top_path=path_helper.abs_src_root,
            skip_dir_patterns=phlb_config.skip_dirs,
            skip_file_patterns=phlb_config.skip_patterns,
        ),
        update_interval_sec=0.5,
        wait=wait,

        backup_path=path,
        backup_name=name
    )
    stats_helper = backup_worker.process()
    return stats_helper
