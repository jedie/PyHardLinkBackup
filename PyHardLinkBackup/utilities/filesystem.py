import hashlib
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Iterable

from bx_py_utils.path import assert_is_dir
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from PyHardLinkBackup.constants import CHUNK_SIZE, HASH_ALGO
from PyHardLinkBackup.utilities.rich_utils import DisplayFileTreeProgress, HumanFileSizeColumn, LargeFileProgress


logger = logging.getLogger(__name__)

MIN_SIZE_FOR_PROGRESS_BAR = CHUNK_SIZE * 10


class RemoveFileOnError:
    def __init__(self, file_path: Path):
        self.file_path = file_path

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if exc_type:
            logger.info(f'Removing incomplete file {self.file_path} due to error: {exc_value}',
                exc_info=(exc_type, exc_value, exc_traceback),
            )
            self.file_path.unlink(missing_ok=True)
            return False


def hash_file(path: Path, progress: DisplayFileTreeProgress, total_size: int) -> str:
    logger.debug('Hash file %s using %s', path, HASH_ALGO)
    hasher = hashlib.new(HASH_ALGO)
    with LargeFileProgress(
        f'Hashing large file: {path.name}',
        parent_progress=progress,
        total_size=total_size,
    ) as progress_bar:
        with path.open('rb') as f:
            while chunk := f.read(CHUNK_SIZE):
                hasher.update(chunk)
                progress_bar.update(advance=len(chunk))
    file_hash = hasher.hexdigest()
    logger.info('%s %s hash: %s', path, HASH_ALGO, file_hash)
    return file_hash


def copy_and_hash(src: Path, dst: Path, progress: DisplayFileTreeProgress, total_size: int) -> str:
    logger.debug('Copy and hash file %s to %s using %s', src, dst, HASH_ALGO)
    hasher = hashlib.new(HASH_ALGO)
    with LargeFileProgress(
        f'Copying large file: {src.name}',
        parent_progress=progress,
        total_size=total_size,
    ) as progress_bar:
        with src.open('rb') as source_file, dst.open('wb') as dst_file:
            while chunk := source_file.read(CHUNK_SIZE):
                dst_file.write(chunk)
                hasher.update(chunk)
                progress_bar.update(advance=len(chunk))

    # Keep original file metadata (permission bits, last access time, last modification time, and flags)
    shutil.copystat(src, dst)

    file_hash = hasher.hexdigest()
    logger.info('%s backup to %s with %s hash: %s', src, dst, HASH_ALGO, file_hash)
    return file_hash


def read_and_hash_file(path: Path) -> tuple[bytes, str]:
    logger.debug('Read and hash file %s using %s into RAM', path, HASH_ALGO)
    content = path.read_bytes()
    hasher = hashlib.new(HASH_ALGO, content)
    file_hash = hasher.hexdigest()
    logger.info('%s %s hash: %s', path, HASH_ALGO, file_hash)
    return content, file_hash


def iter_scandir_files(path: Path, excludes: set[str]) -> Iterable[os.DirEntry]:
    """
    Recursively yield all files+symlinks in the given directory.
    Note: Directory symlinks are treated as files (not recursed into).
    """
    logger.debug('Scanning directory %s', path)
    with os.scandir(path) as scandir_iterator:
        for entry in scandir_iterator:
            if entry.is_dir(
                follow_symlinks=False,  # Handle directory symlinks as files!
            ):
                if entry.name in excludes:
                    logger.debug('Excluding directory %s', entry.path)
                    continue
                yield from iter_scandir_files(Path(entry.path), excludes=excludes)
            else:
                # It's a file or symlink or broken symlink
                yield entry


def humanized_fs_scan(path: Path, excludes: set[str]) -> tuple[int, int]:
    print(f'\nScanning filesystem at: {path}...')

    progress = Progress(
        TimeElapsedColumn(),
        '{task.description}',
        SpinnerColumn('simpleDots'),
        TextColumn('[green]{task.fields[file_count]} Files'),
        '|',
        HumanFileSizeColumn(field_name='total_size'),
        '|',
        TextColumn('[cyan]{task.fields[files_per_sec]} Files/sec'),
    )

    file_count = 0
    total_size = 0
    start_time = time.time()
    scan_task_id = progress.add_task(
        description='Scanning',
        file_count=file_count,
        total_size=total_size,
        files_per_sec=0.0,
        total=None,
    )
    next_update = 0
    with progress:
        for entry in iter_scandir_files(path, excludes=excludes):
            if not entry.is_file():
                # Ignore e.g.: directory symlinks
                continue

            file_count += 1

            try:
                total_size += entry.stat().st_size
            except FileNotFoundError:
                # e.g.: broken symlink
                continue

            now = time.time()
            if now >= next_update:
                elapsed = max(now - start_time, 1e-6)
                files_per_sec = int(file_count / elapsed)
                progress.update(
                    scan_task_id,
                    file_count=file_count,
                    total_size=total_size,
                    files_per_sec=files_per_sec,
                )
                next_update = now + 1

        now = time.time()

        elapsed = max(now - start_time, 1e-6)
        files_per_sec = int(file_count / elapsed)
        progress.stop_task(scan_task_id)
        progress.update(
            scan_task_id,
            description='Completed',
            completed=True,
            file_count=file_count,
            total_size=total_size,
            files_per_sec=files_per_sec,
        )

    return file_count, total_size


def supports_hardlinks(directory: Path) -> bool:
    logger.debug('Checking hardlink support in %s', directory)
    assert_is_dir(directory)
    test_src_file = directory / '.phlb_test'
    test_dst_file = directory / '.phlb_test_link'
    hardlinks_supported = False
    try:
        test_src_file.write_text('test')
        os.link(test_src_file, test_dst_file)
        assert test_dst_file.read_text() == 'test'
        hardlinks_supported = True
    except OSError as err:
        # e.g.: FAT/exFAT filesystems ;)
        logger.exception('Hardlink test failed in %s: %s', directory, err)
    finally:
        test_src_file.unlink(missing_ok=True)
        test_dst_file.unlink(missing_ok=True)

    logger.info('Hardlink support in %s: %s', directory, hardlinks_supported)
    return hardlinks_supported
