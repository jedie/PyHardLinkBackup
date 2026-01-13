import hashlib
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Iterable

from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from PyHardLinkBackup.constants import CHUNK_SIZE, HASH_ALGO
from PyHardLinkBackup.utilities.rich_utils import HumanFileSizeColumn


logger = logging.getLogger(__name__)


def hash_file(path: Path) -> str:
    logger.debug('Hash file %s using %s', path, HASH_ALGO)
    with path.open('rb') as f:
        digest = hashlib.file_digest(f, HASH_ALGO)

    file_hash = digest.hexdigest()
    logger.info('%s %s hash: %s', path, HASH_ALGO, file_hash)
    return file_hash


def copy_and_hash(src: Path, dst: Path) -> str:
    logger.debug('Copy and hash file %s to %s using %s', src, dst, HASH_ALGO)
    hasher = hashlib.new(HASH_ALGO)
    with src.open('rb') as source_file, dst.open('wb') as dst_file:
        while chunk := source_file.read(CHUNK_SIZE):
            dst_file.write(chunk)
            hasher.update(chunk)

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
    """
    logger.debug('Scanning directory %s', path)
    with os.scandir(path) as scandir_iterator:
        for entry in scandir_iterator:
            if entry.is_dir(follow_symlinks=True):
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
        HumanFileSizeColumn(field_name='total_size'),
        TextColumn('| [cyan]{task.fields[files_per_sec]} Files/sec'),
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
