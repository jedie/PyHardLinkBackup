import dataclasses
import datetime
import logging
import os
import sys
import time
from pathlib import Path

from PyHardLinkBackup.logging_setup import LoggingManager
from PyHardLinkBackup.utilities.file_hash_database import FileHashDatabase
from PyHardLinkBackup.utilities.file_size_database import FileSizeDatabase
from PyHardLinkBackup.utilities.filesystem import hash_file, humanized_fs_scan, iter_scandir_files
from PyHardLinkBackup.utilities.humanize import PrintTimingContextManager, human_filesize
from PyHardLinkBackup.utilities.rich_utils import DisplayFileTreeProgress
from PyHardLinkBackup.utilities.sha256sums import check_sha256sums, store_hash
from PyHardLinkBackup.utilities.tee import TeeStdoutContext


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class RebuildResult:
    process_count: int = 0
    process_size: int = 0
    #
    added_size_count: int = 0
    added_hash_count: int = 0
    #
    error_count: int = 0
    #
    hash_verified_count: int = 0
    hash_mismatch_count: int = 0
    hash_not_found_count: int = 0


def rebuild_one_file(
    *,
    backup_root: Path,
    entry: os.DirEntry,
    size_db: FileSizeDatabase,
    hash_db: FileHashDatabase,
    rebuild_result: RebuildResult,
):
    file_path = Path(entry.path)

    # We should ignore all files in the root backup directory itself
    # e.g.: Our *-summary.txt and *.log files
    if file_path.parent == backup_root:
        return

    rebuild_result.process_count += 1

    if entry.name == 'SHA256SUMS':
        # Skip existing SHA256SUMS files
        return

    size = entry.stat().st_size
    rebuild_result.process_size += size

    if size < size_db.MIN_SIZE:
        # Small files will never deduplicate, skip them
        return

    file_hash = hash_file(file_path)

    if size not in size_db:
        size_db.add(size)
        rebuild_result.added_size_count += 1

    if file_hash not in hash_db:
        hash_db[file_hash] = file_path
        rebuild_result.added_hash_count += 1

    # We have calculated the current hash of the file,
    # Let's check if we can verify it, too:
    file_path = Path(entry.path)
    compare_result = check_sha256sums(
        file_path=file_path,
        file_hash=file_hash,
    )
    if compare_result is True:
        rebuild_result.hash_verified_count += 1
    elif compare_result is False:
        rebuild_result.hash_mismatch_count += 1
    elif compare_result is None:
        rebuild_result.hash_not_found_count += 1
        store_hash(
            file_path=file_path,
            file_hash=file_hash,
        )


def rebuild(
    backup_root: Path,
    log_manager: LoggingManager,
) -> RebuildResult:
    backup_root = backup_root.resolve()
    if not backup_root.is_dir():
        print(f'Error: Backup directory "{backup_root}" does not exist!')
        sys.exit(1)

    phlb_conf_dir = backup_root / '.phlb'
    if not phlb_conf_dir.is_dir():
        print(
            f'Error: Backup directory "{backup_root}" seems to be wrong:'
            f' Our hidden ".phlb" configuration directory is missing!'
        )
        sys.exit(1)

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S')
    log_manager.start_file_logging(log_file=backup_root / f'{timestamp}-rebuild.log')

    with PrintTimingContextManager('Filesystem scan completed in'):
        file_count, total_size = humanized_fs_scan(backup_root, excludes={'.phlb'})

        # We should ignore all files in the root backup directory itself
        # e.g.: Our *-summary.txt and *.log files
        for file in backup_root.iterdir():
            if file.is_file():
                file_count -= 1
                total_size -= file.stat().st_size

    with DisplayFileTreeProgress(file_count, total_size) as progress:
        # "Databases" for deduplication
        size_db = FileSizeDatabase(phlb_conf_dir)
        hash_db = FileHashDatabase(backup_root, phlb_conf_dir)

        rebuild_result = RebuildResult()

        next_update = 0
        for entry in iter_scandir_files(backup_root, excludes={'.phlb'}):
            try:
                rebuild_one_file(
                    backup_root=backup_root,
                    entry=entry,
                    size_db=size_db,
                    hash_db=hash_db,
                    rebuild_result=rebuild_result,
                )
            except Exception as err:
                logger.exception(f'Backup {entry.path} {err.__class__.__name__}: {err}')
                rebuild_result.error_count += 1
            else:
                now = time.monotonic()
                if now >= next_update:
                    progress.update(
                        completed_file_count=rebuild_result.process_count, completed_size=rebuild_result.process_size
                    )
                    next_update = now + 0.5

        # Finalize progress indicator values:
        progress.update(completed_file_count=rebuild_result.process_count, completed_size=rebuild_result.process_size)

    summary_file = backup_root / f'{timestamp}-rebuild-summary.txt'
    with TeeStdoutContext(summary_file):
        print(f'\nRebuild "{backup_root}" completed:')
        print(f'  Total files processed: {rebuild_result.process_count}')
        print(f'  Total size processed: {human_filesize(rebuild_result.process_size)}')

        print(f'  Added file size information entries: {rebuild_result.added_size_count}')
        print(f'  Added file hash entries: {rebuild_result.added_hash_count}')

        if rebuild_result.error_count > 0:
            print(f'  Errors during rebuild: {rebuild_result.error_count} (see log for details)')

        print('\nSHA256SUMS verification results:')
        print(f'  Successfully verified files: {rebuild_result.hash_verified_count}')
        print(f'  File hash mismatches: {rebuild_result.hash_mismatch_count}')
        print(f'  File hashes not found, newly stored: {rebuild_result.hash_not_found_count}')

        print()

    logger.info('Rebuild completed. Summary created: %s', summary_file)

    return rebuild_result
