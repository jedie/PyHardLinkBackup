import dataclasses
import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from rich import print  # noqa

from PyHardLinkBackup.constants import CHUNK_SIZE
from PyHardLinkBackup.utilities.file_hash_database import FileHashDatabase
from PyHardLinkBackup.utilities.file_size_database import FileSizeDatabase
from PyHardLinkBackup.utilities.filesystem import (
    copy_and_hash,
    hash_file,
    humanized_fs_scan,
    iter_scandir_files,
    read_and_hash_file,
)
from PyHardLinkBackup.utilities.humanize import human_filesize
from PyHardLinkBackup.utilities.rich_utils import BackupProgress


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class BackupResult:
    backup_dir: Path
    backup_count: int
    backup_size: int
    symlink_files: int
    hardlinked_files: int
    hardlinked_size: int
    copied_files: int
    copied_size: int
    copied_small_files: int
    copied_small_size: int


def backup_tree(*, src_root: Path, backup_root: Path, excludes: set[str]) -> BackupResult:
    src_root = src_root.resolve()
    if not src_root.is_dir():
        print('Error: Source directory does not exist!')
        print(f'Please check source directory: "{src_root}"\n')
        sys.exit(1)

    backup_root = backup_root.resolve()
    if not backup_root.is_dir():
        print('Error: Backup directory does not exist!')
        print(f'Please create "{backup_root}" directory first and start again!\n')
        sys.exit(1)

    # Step 1: Scan source directory:
    src_file_count, src_total_size = humanized_fs_scan(src_root, excludes)

    phlb_conf_dir = backup_root / '.phlb'
    phlb_conf_dir.mkdir(parents=False, exist_ok=True)

    backup_dir = backup_root / src_root.name / datetime.now().strftime('%Y%m%d_%H%M%S')
    logger.info('Backup %s to %s', src_root, backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=False)

    print(f'\nBackup to {backup_dir}...\n')

    with BackupProgress(src_file_count, src_total_size) as progress:
        # "Databases" for deduplication
        size_db = FileSizeDatabase(phlb_conf_dir)
        hash_db = FileHashDatabase(backup_root, phlb_conf_dir)

        backup_count = 0
        backup_size = 0

        symlink_files = 0
        hardlinked_files = 0
        hardlinked_size = 0
        copied_files = 0
        copied_size = 0
        copied_small_files = 0
        copied_small_size = 0

        next_update = 0
        for entry in iter_scandir_files(src_root, excludes=excludes):
            backup_count += 1
            src_path = Path(entry.path)

            dst_path = backup_dir / src_path.relative_to(src_root)
            dst_dir_path = dst_path.parent
            if not dst_dir_path.exists():
                dst_dir_path.mkdir(parents=True, exist_ok=False)

            try:
                size = entry.stat().st_size
            except FileNotFoundError:
                # e.g.: Handle broken symlink
                target = os.readlink(src_path)
                dst_path.symlink_to(target)
                symlink_files += 1
                continue

            backup_size += size

            now = time.monotonic()
            if now >= next_update:
                progress.update(backup_count=backup_count, backup_size=backup_size)
                next_update = now + 0.5

            if entry.is_symlink():
                logger.debug('Copy symlink: %s to %s', src_path, dst_path)
                target = os.readlink(src_path)
                dst_path.symlink_to(target)
                symlink_files += 1
                continue

            # Process regular files
            assert entry.is_file(follow_symlinks=False), f'Unexpected non-file: {src_path}'

            # Deduplication logic

            if size < size_db.MIN_SIZE:
                # Small file -> always copy without deduplication
                logger.info('Copy small file: %s to %s', src_path, dst_path)
                shutil.copy2(src_path, dst_path)
                copied_files += 1
                copied_size += size
                copied_small_files += 1
                copied_small_size += size
                continue

            if size in size_db:
                logger.debug('File with size %iBytes found before -> hash: %s', size, src_path)

                if size <= CHUNK_SIZE:
                    # File can be read complete into memory
                    logger.debug(
                        'File size %iBytes <= CHUNK_SIZE (%iBytes) -> read complete into memory', size, CHUNK_SIZE
                    )
                    file_content, file_hash = read_and_hash_file(src_path)
                    if existing_path := hash_db.get(file_hash):
                        logger.info('Hardlink duplicate file: %s to %s', dst_path, existing_path)
                        os.link(existing_path, dst_path)
                        hardlinked_files += 1
                        hardlinked_size += size
                    else:
                        logger.info('Store unique file: %s to %s', src_path, dst_path)
                        dst_path.write_bytes(file_content)
                        hash_db[file_hash] = dst_path
                        copied_files += 1
                        copied_size += size

                else:
                    # Large file
                    file_hash = hash_file(src_path)  # Calculate hash without copying

                    if existing_path := hash_db.get(file_hash):
                        logger.info('Hardlink duplicate file: %s to %s', dst_path, existing_path)
                        os.link(existing_path, dst_path)
                        hardlinked_files += 1
                        hardlinked_size += size
                    else:
                        logger.info('Copy unique file: %s to %s', src_path, dst_path)
                        hash_db[file_hash] = dst_path
                        copied_files += 1
                        copied_size += size

                # Keep original file metadata (permission bits, time stamps, and flags)
                shutil.copy2(src_path, dst_path)
            else:
                # A file with this size not backuped before -> Can't be duplicate -> copy and hash
                file_hash = copy_and_hash(src_path, dst_path)
                size_db.add(size)
                hash_db[file_hash] = dst_path
                copied_files += 1
                copied_size += size

        # Finalize progress indicator values:
        progress.update(backup_count=backup_count, backup_size=backup_size)

    print(f'\nBackup complete: {backup_dir} (total size {human_filesize(backup_size)})\n')
    print(f'  Total files processed: {backup_count}')
    print(f'   * Symlinked files: {symlink_files}')
    print(f'   * Hardlinked files: {hardlinked_files} (saved {human_filesize(hardlinked_size)})')
    print(f'   * Copied files: {copied_files} (total {human_filesize(copied_size)})')
    print(
        f'     of which small (<{size_db.MIN_SIZE} Bytes) files: {copied_small_files}'
        f' (total {human_filesize(copied_small_size)})'
    )
    print()

    return BackupResult(
        backup_dir=backup_dir,
        backup_count=backup_count,
        backup_size=backup_size,
        symlink_files=symlink_files,
        hardlinked_files=hardlinked_files,
        hardlinked_size=hardlinked_size,
        copied_files=copied_files,
        copied_size=copied_size,
        copied_small_files=copied_small_files,
        copied_small_size=copied_small_size,
    )
