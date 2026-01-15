import dataclasses
import logging
import os
import sys
import time
from pathlib import Path

from PyHardLinkBackup.utilities.file_hash_database import FileHashDatabase
from PyHardLinkBackup.utilities.file_size_database import FileSizeDatabase
from PyHardLinkBackup.utilities.filesystem import hash_file, humanized_fs_scan, iter_scandir_files
from PyHardLinkBackup.utilities.humanize import human_filesize
from PyHardLinkBackup.utilities.rich_utils import BackupProgress


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


def rebuild_one_file(
    *,
    entry: os.DirEntry,
    size_db: FileSizeDatabase,
    hash_db: FileHashDatabase,
    rebuild_result: RebuildResult,
):
    rebuild_result.process_count += 1

    size = entry.stat().st_size
    rebuild_result.process_size += size

    if size < size_db.MIN_SIZE:
        # Small files will never deduplicate, skip them
        return

    file_path = Path(entry.path)
    file_hash = hash_file(file_path)

    if size not in size_db:
        size_db.add(size)
        rebuild_result.added_size_count += 1

    if file_hash not in hash_db:
        hash_db[file_hash] = file_path
        rebuild_result.added_hash_count += 1


def rebuild(backup_root: Path):
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

    file_count, total_size = humanized_fs_scan(backup_root, excludes={'.phlb'})

    with BackupProgress(file_count, total_size) as progress:
        # "Databases" for deduplication
        size_db = FileSizeDatabase(phlb_conf_dir)
        hash_db = FileHashDatabase(backup_root, phlb_conf_dir)

        rebuild_result = RebuildResult()

        next_update = 0
        for entry in iter_scandir_files(backup_root, excludes={'.phlb'}):
            try:
                rebuild_one_file(
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
                    progress.update(backup_count=rebuild_result.process_count, backup_size=rebuild_result.process_size)
                    next_update = now + 0.5

        # Finalize progress indicator values:
        progress.update(backup_count=rebuild_result.process_count, backup_size=rebuild_result.process_size)

    print(f'\nRebuild "{backup_root}" completed:')
    print(f'  Total files processed: {rebuild_result.process_count}')
    print(f'  Total size processed: {human_filesize(rebuild_result.process_size)}')
    print(f'  Added file size information entries: {rebuild_result.added_size_count}')
    print(f'  Added file hash entries: {rebuild_result.added_hash_count}')
    if rebuild_result.error_count > 0:
        print(f'  Errors during rebuild: {rebuild_result.error_count} (see log for details)')
    print()

    return rebuild_result
