import dataclasses
import datetime
import logging
import os
import shutil
import sys
import time
from pathlib import Path

from rich import print  # noqa

from PyHardLinkBackup.constants import CHUNK_SIZE
from PyHardLinkBackup.logging_setup import LoggingManager
from PyHardLinkBackup.utilities.file_hash_database import FileHashDatabase
from PyHardLinkBackup.utilities.file_size_database import FileSizeDatabase
from PyHardLinkBackup.utilities.filesystem import (
    RemoveFileOnError,
    copy_and_hash,
    copy_with_progress,
    hash_file,
    humanized_fs_scan,
    iter_scandir_files,
    read_and_hash_file,
    supports_hardlinks,
    verbose_path_stat,
)
from PyHardLinkBackup.utilities.humanize import PrintTimingContextManager, human_filesize
from PyHardLinkBackup.utilities.rich_utils import DisplayFileTreeProgress
from PyHardLinkBackup.utilities.sha256sums import store_hash
from PyHardLinkBackup.utilities.tee import TeeStdoutContext


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class BackupResult:
    backup_dir: Path
    log_file: Path
    #
    backup_count: int = 0
    backup_size: int = 0
    #
    symlink_files: int = 0
    hardlinked_files: int = 0
    hardlinked_size: int = 0
    #
    copied_files: int = 0
    copied_size: int = 0
    #
    copied_small_files: int = 0
    copied_small_size: int = 0
    #
    error_count: int = 0


def copy_symlink(src_path: Path, dst_path: Path) -> None:
    """
    Copy file and directory symlinks.
    """
    target_is_directory = src_path.is_dir()
    logger.debug('Copy symlink: %s to %s (is directory: %r)', src_path, dst_path, target_is_directory)
    target = os.readlink(src_path)
    dst_path.symlink_to(target, target_is_directory=target_is_directory)


def backup_one_file(
    *,
    src_root: Path,
    entry: os.DirEntry,
    size_db: FileSizeDatabase,
    hash_db: FileHashDatabase,
    backup_dir: Path,
    backup_result: BackupResult,
    progress: DisplayFileTreeProgress,
) -> None:
    backup_result.backup_count += 1
    src_path = Path(entry.path)

    dst_path = backup_dir / src_path.relative_to(src_root)
    dst_dir_path = dst_path.parent
    if not dst_dir_path.exists():
        dst_dir_path.mkdir(parents=True, exist_ok=False)

    try:
        size = entry.stat().st_size
    except FileNotFoundError as err:
        logger.warning(f'Broken symlink {src_path}: {err.__class__.__name__}: {err}')
        copy_symlink(src_path, dst_path)
        backup_result.symlink_files += 1
        return

    backup_result.backup_size += size

    if entry.name == 'SHA256SUMS':
        # Skip existing SHA256SUMS files in source tree,
        # because we create our own SHA256SUMS files.
        logger.debug('Skip existing SHA256SUMS file: %s', src_path)
        return

    if entry.is_symlink():
        copy_symlink(src_path, dst_path)
        backup_result.symlink_files += 1
        return

    # Process regular files
    assert entry.is_file(follow_symlinks=False), f'Unexpected non-file: {src_path}'

    with RemoveFileOnError(dst_path):
        # Deduplication logic

        if size < size_db.MIN_SIZE:
            # Small file -> always copy without deduplication
            logger.info('Copy small file: %s to %s', src_path, dst_path)
            file_hash = copy_and_hash(src_path, dst_path, progress=progress, total_size=size)
            backup_result.copied_files += 1
            backup_result.copied_size += size
            backup_result.copied_small_files += 1
            backup_result.copied_small_size += size
            store_hash(dst_path, file_hash)
            return

        if size in size_db:
            logger.debug('File with size %iBytes found before -> hash: %s', size, src_path)

            if size <= CHUNK_SIZE:
                # File can be read complete into memory
                logger.debug('File size %iBytes <= CHUNK_SIZE (%iBytes) -> read complete into memory', size, CHUNK_SIZE)
                file_content, file_hash = read_and_hash_file(src_path)
                if existing_path := hash_db.get(file_hash):
                    logger.info('Hardlink duplicate file: %s to %s', dst_path, existing_path)
                    os.link(existing_path, dst_path)
                    backup_result.hardlinked_files += 1
                    backup_result.hardlinked_size += size
                else:
                    logger.info('Store unique file: %s to %s', src_path, dst_path)
                    dst_path.write_bytes(file_content)
                    hash_db[file_hash] = dst_path
                    backup_result.copied_files += 1
                    backup_result.copied_size += size

            else:
                # Large file
                file_hash = hash_file(src_path, progress=progress, total_size=size)  # Calculate hash without copying

                if existing_path := hash_db.get(file_hash):
                    logger.info('Hardlink duplicate file: %s to %s', dst_path, existing_path)
                    os.link(existing_path, dst_path)
                    backup_result.hardlinked_files += 1
                    backup_result.hardlinked_size += size
                else:
                    logger.info('Copy unique file: %s to %s', src_path, dst_path)
                    copy_with_progress(src_path, dst_path, progress=progress, total_size=size)
                    hash_db[file_hash] = dst_path
                    backup_result.copied_files += 1
                    backup_result.copied_size += size

            # Keep original file metadata (permission bits, time stamps, and flags)
            shutil.copystat(src_path, dst_path)
        else:
            # A file with this size not backuped before -> Can't be duplicate -> copy and hash
            file_hash = copy_and_hash(src_path, dst_path, progress=progress, total_size=size)
            size_db.add(size)
            hash_db[file_hash] = dst_path
            backup_result.copied_files += 1
            backup_result.copied_size += size

        store_hash(dst_path, file_hash)


def backup_tree(
    *,
    src_root: Path,
    backup_root: Path,
    backup_name: str | None,
    one_file_system: bool,
    excludes: tuple[str, ...],
    log_manager: LoggingManager,
) -> BackupResult:
    src_root = src_root.resolve()
    if not src_root.is_dir():
        print('Error: Source directory does not exist!')
        print(f'Please check source directory: "{src_root}"\n')
        sys.exit(1)

    src_stat = verbose_path_stat(src_root)
    src_device_id = src_stat.st_dev

    backup_root = backup_root.resolve()
    if not backup_root.is_dir():
        print('Error: Backup directory does not exist!')
        print(f'Please create "{backup_root}" directory first and start again!\n')
        sys.exit(1)

    verbose_path_stat(backup_root)

    if not os.access(backup_root, os.W_OK):
        print('Error: No write access to backup directory!')
        print(f'Please check permissions for backup directory: "{backup_root}"\n')
        sys.exit(1)

    if not supports_hardlinks(backup_root):
        print('Error: Filesystem for backup directory does not support hardlinks!')
        print(f'Please check backup directory: "{backup_root}"\n')
        sys.exit(1)

    # Step 1: Scan source directory:
    excludes: set = set(excludes)
    with PrintTimingContextManager('Filesystem scan completed in'):
        src_file_count, src_total_size = humanized_fs_scan(
            path=src_root,
            one_file_system=one_file_system,
            src_device_id=src_device_id,
            excludes=excludes,
        )

    phlb_conf_dir = backup_root / '.phlb'
    phlb_conf_dir.mkdir(parents=False, exist_ok=True)

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S')
    if not backup_name:
        backup_name = src_root.name
    backup_main_dir = backup_root / backup_name
    backup_dir = backup_main_dir / timestamp
    backup_dir.mkdir(parents=True, exist_ok=False)

    log_file = backup_main_dir / f'{timestamp}-backup.log'
    log_manager.start_file_logging(log_file)

    logger.info('Backup %s to %s', src_root, backup_dir)

    print(f'\nBackup to {backup_dir}...\n')

    with DisplayFileTreeProgress(
        description=f'Backup {src_root}...',
        total_file_count=src_file_count,
        total_size=src_total_size,
    ) as progress:
        # "Databases" for deduplication
        size_db = FileSizeDatabase(phlb_conf_dir)
        hash_db = FileHashDatabase(backup_root, phlb_conf_dir)

        backup_result = BackupResult(backup_dir=backup_dir, log_file=log_file)

        next_update = 0
        for entry in iter_scandir_files(
            path=src_root,
            one_file_system=one_file_system,
            src_device_id=src_device_id,
            excludes=excludes,
        ):
            try:
                backup_one_file(
                    src_root=src_root,
                    entry=entry,
                    size_db=size_db,
                    hash_db=hash_db,
                    backup_dir=backup_dir,
                    backup_result=backup_result,
                    progress=progress,
                )
            except Exception as err:
                logger.exception(f'Backup {entry.path} {err.__class__.__name__}: {err}')
                backup_result.error_count += 1
            else:
                now = time.monotonic()
                if now >= next_update:
                    progress.update(
                        completed_file_count=backup_result.backup_count, completed_size=backup_result.backup_size
                    )
                    next_update = now + 0.5

        # Finalize progress indicator values:
        progress.update(completed_file_count=backup_result.backup_count, completed_size=backup_result.backup_size)

    summary_file = backup_main_dir / f'{timestamp}-summary.txt'
    with TeeStdoutContext(summary_file):
        print(f'\nBackup complete: {backup_dir} (total size {human_filesize(backup_result.backup_size)})\n')
        print(f'  Total files processed: {backup_result.backup_count}')
        print(f'   * Symlinked files: {backup_result.symlink_files}')
        print(
            f'   * Hardlinked files: {backup_result.hardlinked_files}'
            f' (saved {human_filesize(backup_result.hardlinked_size)})'
        )
        print(f'   * Copied files: {backup_result.copied_files} (total {human_filesize(backup_result.copied_size)})')
        print(
            f'     of which small (<{size_db.MIN_SIZE} Bytes)'
            f' files: {backup_result.copied_small_files}'
            f' (total {human_filesize(backup_result.copied_small_size)})'
        )
        if backup_result.error_count > 0:
            print(f'  Errors during backup: {backup_result.error_count} (see log for details)')
        print()

    logger.info('Backup completed. Summary created: %s', summary_file)

    return backup_result
