import datetime
import hashlib
import os
import sys

import django
from tqdm import tqdm

from pathlib_revised import Path2 # https://github.com/jedie/pathlib revised/

from PyHardLinkBackup.backup_app.models import BackupRun, BackupEntry
from PyHardLinkBackup.phlb.config import phlb_config


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
    print("\nVerify: %s" % backup_path)

    backup_run = BackupRun.objects.get_from_config_file(backup_path)
    print("\nBackup run:\n%s\n" % backup_run)

    backup_entries = BackupEntry.objects.filter(backup_run = backup_run)
    backup_entries_count = backup_entries.count()
    print("%i File entry exist in database." % backup_entries_count)

    mtime_mismatch = 0

    tqdm_iterator = tqdm(
        backup_entries.iterator(),
        total=backup_entries_count,
        unit=" files",
        leave=True
    )
    for entry in tqdm_iterator:
        entry_path = entry.get_backup_path() # Path2() instance

        if not entry_path.exists():
            print("\nERROR: File not found: %s" % entry_path)
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
            print("\n%s" % entry_path)
            print("ERROR: File size mismatch: %s != %s" % (
                file_stat.st_size, db_file_size
            ))

        hash_file = Path2("%s%s%s" % (entry_path, os.extsep, phlb_config.hash_name))
        if not hash_file.exists():
            print("\n%s" % entry_path)
            print("ERROR: Hash file not found: %s" % hash_file)
            continue

        with hash_file.open("r") as f:
            hash_file_content = f.read().strip()

        db_hash = entry.content_info.hash_hexdigest
        if hash_file_content != db_hash:
            print("\n%s" % entry_path)
            print("ERROR: Hash file mismatch: %s != %s" % (
                hash_file_content, db_hash
            ))

        if fast:
            # Skip verify the file content
            continue

        process_bar_size=phlb_config.chunk_size * 3
        if file_stat.st_size > process_bar_size:
            with tqdm(total=file_stat.st_size, unit='B', unit_scale=True) as process_bar:
                hash_hexdigest = calc_hash(entry_path, process_bar)
        else:
            hash_hexdigest = calc_hash(entry_path, process_bar=None)

        if hash_hexdigest != db_hash:
            print("\n%s" % entry_path)
            print("ERROR: File content changed: Hash mismatch: %s != %s" % (
                hash_hexdigest, db_hash
            ))

    print()

    if fast:
        print("\nWARNING: The '--fast' mode was on:")
        print("The file content was not verified!")

    if mtime_mismatch:
        print("\nINFO: %i files have different modify timestamps!" % mtime_mismatch)

    print("\nVerify done.")



if __name__ == '__main__':
    backup_path=os.path.expanduser(
        # "~/PyHardLinkBackups/PyHardLinkBackup"
        "~/PyHardLinkBackups/PyHardLinkBackup/2016-01-29-160915"
    )
    verify_backup(backup_path,
        fast=True
        # fast=False
    )
