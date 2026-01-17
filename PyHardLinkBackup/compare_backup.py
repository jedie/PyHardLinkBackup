import dataclasses
import datetime
import logging
import os
import sys
import time
from pathlib import Path

from rich import print  # noqa

from PyHardLinkBackup.logging_setup import LoggingManager
from PyHardLinkBackup.utilities.file_hash_database import FileHashDatabase
from PyHardLinkBackup.utilities.file_size_database import FileSizeDatabase
from PyHardLinkBackup.utilities.filesystem import (
    hash_file,
    humanized_fs_scan,
    iter_scandir_files,
)
from PyHardLinkBackup.utilities.humanize import PrintTimingContextManager, human_filesize
from PyHardLinkBackup.utilities.rich_utils import DisplayFileTreeProgress
from PyHardLinkBackup.utilities.tee import TeeStdoutContext


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class CompareResult:
    last_timestamp: str
    compare_dir: Path
    log_file: Path
    #
    total_file_count: int = 0
    total_size: int = 0
    #
    src_file_new_count: int = 0
    file_size_missmatch: int = 0
    file_hash_missmatch: int = 0
    #
    small_file_count: int = 0
    size_db_missing_count: int = 0
    hash_db_missing_count: int = 0
    #
    successful_file_count: int = 0
    error_count: int = 0


def compare_one_file(
    *,
    src_root: Path,
    entry: os.DirEntry,
    size_db: FileSizeDatabase,
    hash_db: FileHashDatabase,
    compare_dir: Path,
    compare_result: CompareResult,
) -> None:
    src_size = entry.stat().st_size

    # For the progress bars:
    compare_result.total_file_count += 1
    compare_result.total_size += src_size

    src_path = Path(entry.path)
    dst_path = compare_dir / src_path.relative_to(src_root)

    if not dst_path.exists():
        logger.warning('Source file %s not found in compare %s', src_path, dst_path)
        compare_result.src_file_new_count += 1
        return

    dst_size = dst_path.stat().st_size
    if src_size != dst_size:
        logger.warning(
            'Source file %s size (%i Bytes) differs from compare file %s size (%iBytes)',
            src_path,
            src_size,
            dst_path,
            dst_size,
        )
        compare_result.file_size_missmatch += 1
        return

    src_hash = hash_file(src_path)
    dst_hash = hash_file(dst_path)

    if src_hash != dst_hash:
        logger.warning(
            'Source file %s hash %r differs from compare file %s hash (%s)',
            src_path,
            src_hash,
            dst_path,
            dst_hash,
        )
        compare_result.file_hash_missmatch += 1
        return

    if src_size < size_db.MIN_SIZE:
        # Small file -> Not in deduplication database
        compare_result.small_file_count += 1
    else:
        if src_size not in size_db:
            logger.warning(
                'Source file %s size (%i Bytes) not found in deduplication database',
                src_path,
                src_size,
            )
            compare_result.size_db_missing_count += 1

        if src_hash not in hash_db:
            logger.warning(
                'Source file %s hash %r not found in deduplication database',
                src_path,
                src_hash,
            )
            compare_result.hash_db_missing_count += 1

    # Everything is ok
    compare_result.successful_file_count += 1


def compare_tree(
    *,
    src_root: Path,
    backup_root: Path,
    excludes: tuple[str, ...],
    log_manager: LoggingManager,
) -> CompareResult:
    src_root = src_root.resolve()
    if not src_root.is_dir():
        print('Error: Source directory does not exist!')
        print(f'Please check source directory: "{src_root}"\n')
        sys.exit(1)

    backup_root = backup_root.resolve()
    phlb_conf_dir = backup_root / '.phlb'
    if not phlb_conf_dir.is_dir():
        print('Error: Compare directory seems to be wrong! (No .phlb configuration directory found)')
        print(f'Please check backup directory: "{backup_root}"\n')
        sys.exit(1)

    compare_main_dir = backup_root / src_root.name
    timestamps = sorted(
        path.name for path in compare_main_dir.iterdir() if path.is_dir() and path.name.startswith('20')
    )
    print(f'Found {len(timestamps)} compare(s) in {compare_main_dir}:')
    for timestamp in timestamps:
        print(f' * {timestamp}')
    last_timestamp = timestamps[-1]
    compare_dir = compare_main_dir / last_timestamp
    print(f'\nComparing source tree {src_root} with {last_timestamp} compare:')
    print(f'  {compare_dir}\n')

    now_timestamp = datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S')
    log_file = compare_main_dir / f'{now_timestamp}-compare.log'
    log_manager.start_file_logging(log_file)

    excludes: set = set(excludes)
    with PrintTimingContextManager('Filesystem scan completed in'):
        src_file_count, src_total_size = humanized_fs_scan(src_root, excludes=excludes)

    with DisplayFileTreeProgress(src_file_count, src_total_size) as progress:
        # init "databases":
        size_db = FileSizeDatabase(phlb_conf_dir)
        hash_db = FileHashDatabase(backup_root, phlb_conf_dir)

        compare_result = CompareResult(last_timestamp=last_timestamp, compare_dir=compare_dir, log_file=log_file)

        next_update = 0
        for entry in iter_scandir_files(src_root, excludes=excludes):
            try:
                compare_one_file(
                    src_root=src_root,
                    entry=entry,
                    size_db=size_db,
                    hash_db=hash_db,
                    compare_dir=compare_dir,
                    compare_result=compare_result,
                )
            except Exception as err:
                logger.exception(f'Compare {entry.path} {err.__class__.__name__}: {err}')
                compare_result.error_count += 1
            else:
                now = time.monotonic()
                if now >= next_update:
                    progress.update(
                        completed_file_count=compare_result.total_file_count,
                        completed_size=compare_result.total_size,
                    )
                    next_update = now + 0.5

        # Finalize progress indicator values:
        progress.update(completed_file_count=compare_result.total_file_count, completed_size=compare_result.total_size)

    summary_file = compare_main_dir / f'{now_timestamp}-summary.txt'
    with TeeStdoutContext(summary_file):
        print(f'\nCompare complete: {compare_dir} (total size {human_filesize(compare_result.total_size)})\n')
        print(f'  Total files processed: {compare_result.total_file_count}')
        print(f'   * Successful compared files: {compare_result.successful_file_count}')
        print(f'   * New source files: {compare_result.src_file_new_count}')
        print(f'   * File size missmatch: {compare_result.file_size_missmatch}')
        print(f'   * File hash missmatch: {compare_result.file_hash_missmatch}')

        print(f'   * Small (<{size_db.MIN_SIZE} Bytes) files: {compare_result.small_file_count}')
        print(f'   * Missing in size DB: {compare_result.size_db_missing_count}')
        print(f'   * Missing in hash DB: {compare_result.hash_db_missing_count}')

        if compare_result.error_count > 0:
            print(f'  Errors during compare: {compare_result.error_count} (see log for details)')
        print()

    logger.info('Compare completed. Summary created: %s', summary_file)

    return compare_result
