import hashlib
import os

# https://github.com/tqdm/tqdm
from tqdm import tqdm

import django

# https://github.com/jedie/pathlib_revised/
from pathlib_revised import Path2

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.backup_app.models import BackupEntry, BackupRun
from pyhardlinkbackup.phlb.config import phlb_config


def calc_hash(entry_path, process_bar=None):
    with entry_path.open("rb") as f:
        hash = hashlib.new(phlb_config.hash_name)
        while True:
            data = f.read(phlb_config.chunk_size)
            if not data:
                break

            hash.update(data)
            if process_bar:
                process_bar.update(len(data))
    return hash.hexdigest()


def verify_backup(backup_path, fast):
    django.setup()

    backup_path = Path2(backup_path).resolve()
    print(f"\nVerify: {backup_path}")

    backup_run = BackupRun.objects.get_from_config_file(backup_path)
    print(f"\nBackup run:\n{backup_run}\n")

    backup_entries = BackupEntry.objects.filter(backup_run=backup_run)
    backup_entries_count = backup_entries.count()
    print(f"{backup_entries_count:d} File entry exist in database.")

    mtime_mismatch = 0

    tqdm_iterator = tqdm(
        backup_entries.iterator(),
        total=backup_entries_count,
        unit=" files",
        leave=True)
    for entry in tqdm_iterator:
        entry_path = entry.get_backup_path()  # Path2() instance

        if not entry_path.exists():
            print(f"\nERROR: File not found: {entry_path}")
            continue

        file_stat = entry_path.stat()
        if file_stat.st_mtime_ns != entry.file_mtime_ns:
            mtime_mismatch += 1
        #     print("\n%s" % entry_path)
        #     print("WARNING: modify timestamp mismatch: %s != %s" % (
        #         file_stat.st_mtime_ns, entry.file_mtime_ns
        #     ))

        db_file_size = entry.content_info.file_size
        if file_stat.st_size != db_file_size:
            print(f"\n{entry_path}")
            print(f"ERROR: File size mismatch: {file_stat.st_size} != {db_file_size}")

        hash_file = Path2(f"{entry_path}{os.extsep}{phlb_config.hash_name}")
        if not hash_file.exists():
            print(f"\n{entry_path}")
            print(f"ERROR: Hash file not found: {hash_file}")
            continue

        with hash_file.open("r") as f:
            hash_file_content = f.read().strip()

        db_hash = entry.content_info.hash_hexdigest
        if hash_file_content != db_hash:
            print(f"\n{entry_path}")
            print(f"ERROR: Hash file mismatch: {hash_file_content} != {db_hash}")

        if fast:
            # Skip verify the file content
            continue

        process_bar_size = phlb_config.chunk_size * 3
        if file_stat.st_size > process_bar_size:
            with tqdm(total=file_stat.st_size, unit="B", unit_scale=True) as process_bar:
                hash_hexdigest = calc_hash(entry_path, process_bar)
        else:
            hash_hexdigest = calc_hash(entry_path, process_bar=None)

        if hash_hexdigest != db_hash:
            print(f"\n{entry_path}")
            print(
                f"ERROR: File content changed: Hash mismatch: {hash_hexdigest} != {db_hash}")

    print()

    if fast:
        print("\nWARNING: The '--fast' mode was on:")
        print("The file content was not verified!")

    if mtime_mismatch:
        print(f"\nINFO: {mtime_mismatch:d} files have different modify timestamps!")

    print("\nVerify done.")


if __name__ == "__main__":
    backup_path = os.path.expanduser(
        # "~/pyhardlinkbackups/pyhardlinkbackup"
        "~/pyhardlinkbackups/pyhardlinkbackup/2016-01-29-160915"
    )
    verify_backup(
        backup_path,
        fast=True
        # fast=False
    )
