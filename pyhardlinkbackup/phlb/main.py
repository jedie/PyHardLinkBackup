"""
    Python HardLink Backup
    ~~~~~~~~~~~~~~~~~~~~~~

    :copyleft: 2015-2020 by Jens Diemer
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""


import logging
import pprint

from django.conf import settings

# https://github.com/jedie/pathlib_revised/
from pathlib_revised import DirEntryPath
from pathlib_revised.pathlib import Path2, pprint_path

# https://github.com/jedie/IterFilesystem
from iterfilesystem.humanize import human_filesize, human_time
from iterfilesystem.iter_scandir import ScandirWalker
from iterfilesystem.main import IterFilesystem

# https://github.com/jedie/PyHardLinkBackup
import pyhardlinkbackup
from pyhardlinkbackup.backup_app.models import BackupEntry, BackupRun
from pyhardlinkbackup.phlb.backup import FileBackup
from pyhardlinkbackup.phlb.config import phlb_config
from pyhardlinkbackup.phlb.exceptions import BackupFileError
from pyhardlinkbackup.phlb.humanize import dt2naturaltimesince, ns2naturaltimesince, to_percent
from pyhardlinkbackup.phlb.path_helper import PathHelper
from pyhardlinkbackup.phlb.traceback_plus import exc_plus

log = logging.getLogger(__name__)


class BackupIterFilesystem(IterFilesystem):
    def __init__(self, *, path_helper, **kwargs):
        phlb_config.log_config(level=logging.DEBUG)

        super().__init__(**kwargs)

        self.path_helper = path_helper

    def start(self):
        old_backups = BackupRun.objects.filter(name=self.path_helper.backup_name)
        log.info(f"{self.path_helper.backup_name!r} was backuped {old_backups.count():d} time(s)")

        old_backups = old_backups.filter(completed=True)
        completed_count = old_backups.count()
        log.info(f"There are {completed_count:d} backups finished completed.")

        self.latest_backup = None
        self.latest_mtime_ns = None
        try:
            self.latest_backup = old_backups.latest()
        except BackupRun.DoesNotExist:
            log.info(f"No old backup found with name {self.path_helper.backup_name!r}")
        else:
            latest_backup_datetime = self.latest_backup.backup_datetime
            log.info("Latest backup from: %s", dt2naturaltimesince(latest_backup_datetime))

            backup_entries = BackupEntry.objects.filter(backup_run=self.latest_backup)
            try:
                latest_entry = backup_entries.latest()
            except BackupEntry.DoesNotExist:
                log.warning("Latest backup run contains no files?!?")
            else:
                self.latest_mtime_ns = latest_entry.file_mtime_ns
                log.info(
                    "Latest backup entry modified time: %s",
                    ns2naturaltimesince(self.latest_mtime_ns)
                )

        log.info(f"Backup to: '{self.path_helper.abs_dst_root}'")
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
        log.debug(" * backup_run: %s", self.backup_run)

        log.info(f"Start backup: {self.path_helper.time_string}")
        log.info(f"Source path: {self.path_helper.abs_src_root}")

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
            log.debug("Fast compare: source file is newer than latest backuped file.")
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
            log.debug("Fast compare: File size is different: %s != %s", file_size, dir_path.stat.st_size)
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
            # log.info("TODO Symlink: %s" % dir_path)
            return

        if dir_path.resolve_error is not None:
            log.info(f"TODO resolve error: {dir_path.resolve_error}")
            pprint_path(dir_path)
            return

        if dir_path.different_path:
            log.info("TODO different path:")
            pprint_path(dir_path)
            return

        if dir_path.is_dir:
            # log.info("TODO dir: %s" % dir_path)
            return

        if dir_path.is_file:
            # log.info("Normal file: %s", dir_path)

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
            try:
                if old_backup_entry is not None:
                    # We can just link the file from a old backup
                    file_backup.fast_deduplication_backup(old_backup_entry)
                else:
                    file_backup.deduplication_backup()
            except BackupFileError as err:
                # A error occur while backup the file
                log.error(err.args[0])
                self.stats_helper.process_error_count += 1
                return

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
            log.info("TODO: %s", dir_path)
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
            f' * Files to backup: {stats.walker_file_count} files',
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

    def done(self):
        if self.stats_helper.abort is True:
            # KeyboardInterrupt catch in iterfilesystem.main.IterFilesystem.process
            log.info(
                '\n *** Abort backup, because user hits the interrupt key during execution! ***\n'
            )
        elif self.stats_helper.abort is None:
            log.info('\nWARNING: Unknown scan abort!\n')

        self.backup_run.completed = True
        self.backup_run.save(update_fields=['completed'])

        log.debug(f'stats={self.stats_helper.pformat()}')

        log.info("\n%s\n" % "\n".join(self.get_summary()))
        log.info('---END---')


class LogPathMaker:
    """
    Link or copy the log file to backup
    """

    def __init__(self, path_helper):
        self.path_helper = path_helper

    def __enter__(self):
        # make temp file available in destination via link ;)
        self.temp_log_path = Path2(settings.LOG_FILEPATH)
        assert self.temp_log_path.is_file(), f"{settings.LOG_FILEPATH} doesn't exists?!?"

        self.path_helper.log_filepath.parent.makedirs(  # calls os.makedirs()
            mode=phlb_config.default_new_path_mode, exist_ok=True
        )

        assert self.path_helper.log_filepath.exists() is False, \
            f'Already exists: {self.path_helper.log_filepath}'

        try:
            self.temp_log_path.link(self.path_helper.log_filepath)  # call os.link()
        except OSError as err:
            # e.g.:
            # temp is on a other drive than the destination
            log.error(f"Can't link log file: {err}")
            self.copy_log = True
        else:
            self.copy_log = False

    def __exit__(self, exc_type, exc_val, exc_tb):
        log.info('Log file saved here: %s', self.path_helper.log_filepath)
        if self.copy_log:
            log.warning(f"copy log file from '{settings.LOG_FILEPATH}' to '{self.path_helper.log_filepath}'")
            self.temp_log_path.copyfile(self.path_helper.log_filepath)  # call shutil.copyfile()


def backup(path, name, wait=False):
    path_helper = PathHelper(src_path=path, force_name=name)

    # add some informations into log files:
    log.debug(f"PyHardLinkBackup v{pyhardlinkbackup.__version__}")

    scan_dir_kwargs = dict(
        top_path=path_helper.abs_src_root,
        skip_dir_patterns=phlb_config.skip_dirs,
        skip_file_patterns=phlb_config.skip_patterns,
    )
    log.debug('Scandir settings: %s', pprint.pformat(scan_dir_kwargs))

    stats_helper = None
    with LogPathMaker(path_helper):
        try:
            backup_worker = BackupIterFilesystem(
                ScanDirClass=ScandirWalker,
                scan_dir_kwargs=scan_dir_kwargs,
                update_interval_sec=0.5,
                wait=wait,

                path_helper=path_helper,
            )
            stats_helper = backup_worker.process()
        except KeyboardInterrupt:
            log.warning('Abort backup, because user hits the interrupt key during execution!')
        except BaseException:
            log.error("_" * 79)
            log.error("ERROR: Backup aborted with a unexpected error:")
            for line in exc_plus():
                log.error(line)
            log.error("-" * 79)
            log.error("Please report this Bug here:")
            log.error("https://github.com/jedie/PyHardLinkBackup/issues/new")
            log.error("-" * 79)

    return stats_helper
