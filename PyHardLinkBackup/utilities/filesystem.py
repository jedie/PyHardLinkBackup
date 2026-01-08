import hashlib
import os
from pathlib import Path
from typing import Iterable

from PyHardLinkBackup.constants import CHUNK_SIZE, HASH_ALGO


def hash_file(path: Path) -> str:
    with path.open('rb') as f:
        digest = hashlib.file_digest(f, HASH_ALGO)
    return digest.hexdigest()


def copy_and_hash(src: Path, dst: Path) -> str:
    h = hashlib.new(HASH_ALGO)
    with src.open('rb') as fsrc, dst.open('wb') as fdst:
        while chunk := fsrc.read(CHUNK_SIZE):
            fdst.write(chunk)
            h.update(chunk)
    return h.hexdigest()


def iter_scandir_files(path: Path) -> Iterable[os.DirEntry]:
    """
    Recursively yield all files+symlinks in the given directory.
    """
    for entry in os.scandir(path):
        if entry.is_file(follow_symlinks=True):
            yield entry
        elif entry.is_dir(follow_symlinks=True):
            yield from iter_scandir_files(Path(entry.path))
