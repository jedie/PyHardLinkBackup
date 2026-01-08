import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from PyHardLinkBackup.constants import SMALL_FILE_THRESHOLD
from PyHardLinkBackup.utilities.file_size_database import FileSizeDatabase
from PyHardLinkBackup.utilities.filesystem import copy_and_hash, hash_file, iter_scandir_files


logger = logging.getLogger(__name__)


def backup_tree(src_root: Path, backup_root: Path):
    # Create new snapshot dir
    snapshot_dir = backup_root / datetime.now().strftime('%Y%m%d_%H%M%S')
    snapshot_dir.mkdir(parents=True, exist_ok=False)

    # Databases for deduplication
    size_db = FileSizeDatabase(backup_root)
    hash_db = {}  # hash -> path

    for entry in iter_scandir_files(src_root):
        src_path = src_root / entry.name
        dst_path = snapshot_dir / entry.name
        if entry.is_symlink():
            # Copy symlinks as-is
            target = os.readlink(src_path)
            dst_path.symlink_to(target)
            continue

        # Process regular files
        assert entry.is_file(follow_symlinks=False), f'Unexpected non-file: {src_path}'
        size = entry.stat().st_size
        if size < SMALL_FILE_THRESHOLD:
            shutil.copy2(src_path, dst_path)
            # No dedup for small files
            continue

        # Deduplication logic
        size_known = size in size_db
        if not size_known:
            # No file with this size seen, copy and hash
            file_hash = copy_and_hash(src_path, dst_path)
            size_db.add(size)
            hash_db[file_hash] = dst_path
        else:
            # Size match, hash and check
            file_hash = hash_file(src_path)

            if existing_path := hash_db.get(file_hash):
                # Hardlink to existing file
                os.link(existing_path, dst_path)
            else:
                # New unique file -> copy
                shutil.copy2(src_path, dst_path)
                hash_db[file_hash] = dst_path

    print(f'Backup complete: {snapshot_dir}')
