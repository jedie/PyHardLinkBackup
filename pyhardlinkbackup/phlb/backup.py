import hashlib
import logging
import time
from timeit import default_timer

import psutil

# https://github.com/jedie/IterFilesystem
from iterfilesystem.humanize import human_filesize

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.backup_app.models import BackupEntry
from pyhardlinkbackup.phlb.config import phlb_config
from pyhardlinkbackup.phlb.deduplicate import deduplicate
from pyhardlinkbackup.phlb.exceptions import BackupFileError

log = logging.getLogger(__name__)


class FileBackup:
    """
    backup one file
    """
    MIN_CHUNK_SIZE = phlb_config.min_chunk_size
    MAX_CHUNK_SIZE = int(psutil.virtual_memory().available * 0.9)

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

        log.debug('min chunk size: %i Bytes', self.MIN_CHUNK_SIZE)
        log.debug('max chunk size: %i Bytes', self.MAX_CHUNK_SIZE)
        self.chunk_size = self.MIN_CHUNK_SIZE

        if self._SIMULATE_SLOW_SPEED:
            log.error("Slow down speed for tests activated!")

    def _deduplication_backup(self, *, in_file, out_file):

        file_size = self.dir_path.stat.st_size
        small_file = file_size < self.chunk_size

        hash = hashlib.new(phlb_config.hash_name)
        process_size = 0
        big_file = False

        while True:
            start_time = default_timer()
            try:
                data = in_file.read(self.chunk_size)
            except MemoryError:
                # Lower the chunk size to avoid memory errors
                while self.chunk_size > self.MIN_CHUNK_SIZE:
                    self.chunk_size = int(self.chunk_size * 0.25)
                    try:
                        data = in_file.read(self.chunk_size)
                    except MemoryError:
                        continue
                    else:
                        self.MAX_CHUNK_SIZE = self.chunk_size
                        log.warning('set max block size to: %i Bytes.', self.MAX_CHUNK_SIZE)
                        break

            if not data:
                break

            if self._SIMULATE_SLOW_SPEED:
                log.error("Slow down speed for tests!")
                time.sleep(self._SIMULATE_SLOW_SPEED)

            out_file.write(data)
            hash.update(data)

            chunk_size = len(data)
            process_size += chunk_size

            if not small_file and chunk_size == self.chunk_size:
                # Display "current file processbar", but only for big files

                # Calculate the chunk size, so we update the current file bar
                # in self.update_interval_sec intervals
                duration = default_timer() - start_time
                throughput = chunk_size / duration
                new_chunk_size = throughput * self.worker.update_interval_sec

                chunk_size = int((new_chunk_size + chunk_size) / 2)
                if chunk_size < self.MIN_CHUNK_SIZE:
                    chunk_size = self.MIN_CHUNK_SIZE
                if chunk_size > self.MAX_CHUNK_SIZE:
                    chunk_size = self.MAX_CHUNK_SIZE

                self.chunk_size = chunk_size

                if not big_file:
                    # init current file bar
                    self.process_bars.file_bar.reset(total=file_size)
                    big_file = True

                # print the bar:
                self.process_bars.file_bar.desc = (
                    f'{self.dir_path.path_instance.name}'
                    f' | {human_filesize(self.chunk_size)} chunks'
                    f' | {duration:.1f} sec.'
                )
                self.process_bars.file_bar.update(process_size)

                self.worker.update(  # Update statistics and global bars
                    dir_entry=self.dir_path.path_instance,
                    file_size=process_size,
                    process_bars=self.process_bars
                )
                process_size = 0

        if big_file:
            self.process_bars.file_bar.update(process_size)
            self.worker.update(
                dir_entry=self.dir_path.path_instance,
                file_size=process_size,
                process_bars=self.process_bars
            )
        else:
            # Always update the global statistics / process bars:
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

            # Always update the global statistics / process bars:
            self.worker.update(
                dir_entry=self.dir_path.path_instance,
                file_size=self.dir_path.stat.st_size,
                process_bars=self.process_bars
            )

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
                    f"Skip file {self.worker.path_helper.abs_src_filepath} error: {err}"
                )
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
