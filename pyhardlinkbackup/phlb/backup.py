#
import hashlib
import logging
import time

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.backup_app.models import BackupEntry
from pyhardlinkbackup.phlb.config import phlb_config
from pyhardlinkbackup.phlb.deduplicate import deduplicate

log = logging.getLogger(f"phlb.{__name__}")


class BackupFileError(Exception):
    pass


class FileBackup:
    """
    backup one file
    """

    # TODO: remove with Mock solution:
    _SIMULATE_SLOW_SPEED = False  # for unittests only!

    def __init__(self, *, dir_path, worker, process_bars):
        """
        :param dir_path: DirEntryPath() instance of the source file
        :param path_helper: PathHelper(backup_root) instance
        """
        self.dir_path = dir_path
        self.worker = worker
        self.process_bars = process_bars

        self.fast_backup = None  # Was a fast backup used?
        self.file_linked = None  # Was a hardlink used?

        if self._SIMULATE_SLOW_SPEED:
            log.error("Slow down speed for tests activated!")

    def _deduplication_backup(self, *, in_file, out_file):

        collect_file_size = self.dir_path.stat.st_size
        big_file = collect_file_size > 10 * 1024 * 1024  # FIXME: Calc dynamic

        if big_file:
            self.process_bars.file_bar.desc = f'Backup "{self.dir_path.path_instance.name}"'
            self.process_bars.file_bar.reset(total=collect_file_size)

        hash = hashlib.new(phlb_config.hash_name)
        process_size = 0
        while True:
            data = in_file.read(phlb_config.chunk_size)
            if not data:
                break

            if self._SIMULATE_SLOW_SPEED:
                log.error("Slow down speed for tests!")
                time.sleep(self._SIMULATE_SLOW_SPEED)

            out_file.write(data)
            hash.update(data)

            process_size += len(data)
            if big_file and self.worker.update_file_interval:
                self.process_bars.file_bar.update(process_size)
                self.worker.update(
                    dir_entry=self.dir_path.path_instance,
                    file_size=process_size,
                    process_bars=self.process_bars
                )
                process_size = 0

        if big_file:
            file_size = process_size
        else:
            file_size = collect_file_size

        self.process_bars.file_bar.update(process_size)
        self.worker.update(
            dir_entry=self.dir_path.path_instance,
            file_size=file_size,
            process_bars=self.process_bars
        )

        return hash

    def fast_deduplication_backup(self, old_backup_entry):
        """
        We can just link a old backup entry

        :param latest_backup: old BackupEntry model instance
        """
        # TODO: merge code with parts from deduplication_backup()
        src_path = self.dir_path.resolved_path
        log.debug("*** fast deduplication backup: '%s'", src_path)
        old_file_path = old_backup_entry.get_backup_path()

        if not self.worker.path_helper.abs_dst_path.is_dir():
            try:
                self.worker.path_helper.abs_dst_path.makedirs(
                    mode=phlb_config.default_new_path_mode)
            except OSError as err:
                raise BackupFileError(f"Error creating out path: {err}")
        else:
            assert not self.worker.path_helper.abs_dst_filepath.is_file(), (
                f"Out file already exists: {self.worker.path_helper.abs_src_filepath!r}"
            )

        with self.worker.path_helper.abs_dst_hash_filepath.open("w") as hash_file:
            try:
                old_file_path.link(self.worker.path_helper.abs_dst_filepath)  # call os.link()
            except OSError as err:
                log.error(f"Can't link '{old_file_path}' to '{self.worker.path_helper.abs_dst_filepath}': {err}")
                log.info("Mark %r with 'no link source'.", old_backup_entry)
                old_backup_entry.no_link_source = True
                old_backup_entry.save()

                # do a normal copy backup
                self.deduplication_backup()
                return

            hash_hexdigest = old_backup_entry.content_info.hash_hexdigest
            hash_file.write(hash_hexdigest)

        BackupEntry.objects.create(
            backup_run=self.worker.backup_run,
            backup_entry_path=self.worker.path_helper.abs_dst_filepath,
            hash_hexdigest=hash_hexdigest,
        )

        if self._SIMULATE_SLOW_SPEED:
            log.error("Slow down speed for tests!")
            time.sleep(self._SIMULATE_SLOW_SPEED)

        self.fast_backup = True  # Was a fast backup used?
        self.file_linked = True  # Was a hardlink used?

    def deduplication_backup(self):
        """
        Backup the current file and compare the content.
        """
        self.fast_backup = False  # Was a fast backup used?

        src_path = self.dir_path.resolved_path
        log.debug("*** deduplication backup: '%s'", src_path)

        log.debug("abs_src_filepath: '%s'", self.worker.path_helper.abs_src_filepath)
        log.debug("abs_dst_filepath: '%s'", self.worker.path_helper.abs_dst_filepath)
        log.debug("abs_dst_hash_filepath: '%s'", self.worker.path_helper.abs_dst_hash_filepath)
        log.debug("abs_dst_dir: '%s'", self.worker.path_helper.abs_dst_path)

        if not self.worker.path_helper.abs_dst_path.is_dir():
            try:
                self.worker.path_helper.abs_dst_path.makedirs(
                    mode=phlb_config.default_new_path_mode)
            except OSError as err:
                raise BackupFileError(f"Error creating out path: {err}")
        else:
            assert not self.worker.path_helper.abs_dst_filepath.is_file(), (
                f"Out file already exists: {self.worker.path_helper.abs_src_filepath!r}"
            )

        try:
            try:
                with self.worker.path_helper.abs_src_filepath.open("rb") as in_file:
                    with self.worker.path_helper.abs_dst_hash_filepath.open("w") as hash_file:
                        with self.worker.path_helper.abs_dst_filepath.open("wb") as out_file:

                            hash = self._deduplication_backup(
                                in_file=in_file,
                                out_file=out_file
                            )

                        hash_hexdigest = hash.hexdigest()
                        hash_file.write(hash_hexdigest)
            except OSError as err:
                # FIXME: Better error message
                raise BackupFileError(
                    f"Skip file {self.worker.path_helper.abs_src_filepath} error: {err}")
        except KeyboardInterrupt:
            # Try to remove created files
            try:
                self.worker.path_helper.abs_dst_filepath.unlink()
            except OSError:
                pass

            try:
                self.worker.path_helper.abs_dst_hash_filepath.unlink()
            except OSError:
                pass

            raise KeyboardInterrupt

        old_backup_entry = deduplicate(self.worker.path_helper.abs_dst_filepath, hash_hexdigest)
        if old_backup_entry is None:
            log.debug("File is unique.")
            self.file_linked = False  # Was a hardlink used?
        else:
            log.debug(f"File was deduplicated via hardlink to: {old_backup_entry}")
            self.file_linked = True  # Was a hardlink used?

        # set origin access/modified times to the new created backup file
        atime_ns = self.dir_path.stat.st_atime_ns
        mtime_ns = self.dir_path.stat.st_mtime_ns
        self.worker.path_helper.abs_dst_filepath.utime(ns=(atime_ns, mtime_ns))  # call os.utime()
        log.debug(f"Set mtime to: {mtime_ns}")

        BackupEntry.objects.create(
            backup_run=self.worker.backup_run,
            backup_entry_path=self.worker.path_helper.abs_dst_filepath,
            hash_hexdigest=hash_hexdigest,
        )

        self.fast_backup = False  # Was a fast backup used?
