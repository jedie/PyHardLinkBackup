"""
    Python HardLink Backup
    ~~~~~~~~~~~~~~~~~~~~~~

    :copyleft: 2016-2019 by Jens Diemer
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""

import datetime
import hashlib
import logging
import os

import django
from click._compat import strip_ansi

# https://github.com/jedie/pathlib_revised/
from pathlib_revised import DirEntryPath, Path2

# https://github.com/jedie/IterFilesystem
from iterfilesystem.humanize import human_filesize
from iterfilesystem.iter_scandir import ScandirWalker
from iterfilesystem.statistic_helper import StatisticHelper

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.backup_app.models import BackupEntry, BackupRun
from pyhardlinkbackup.phlb import BACKUP_RUN_CONFIG_FILENAME
from pyhardlinkbackup.phlb.config import phlb_config
from pyhardlinkbackup.phlb.deduplicate import deduplicate
from pyhardlinkbackup.phlb.filesystem_walk import scandir_limited
from pyhardlinkbackup.phlb.humanize import to_percent
from pyhardlinkbackup.phlb.traceback_plus import exc_plus

try:
    # https://github.com/tqdm/tqdm
    from tqdm import tqdm
except ImportError as err:
    raise ImportError(f"Please install 'tqdm': {err}")


log = logging.getLogger(f"phlb.{__name__}")


def calculate_hash(f, callback):
    # TODO: merge code!
    hash = hashlib.new(phlb_config.hash_name)
    f.seek(0)
    while True:
        data = f.read(phlb_config.chunk_size)
        if not data:
            break

        hash.update(data)
        callback(data)

    return hash


class HashCallback:
    def __init__(self, process_bar):
        self.process_bar = process_bar

    def __call__(self, data):
        self.process_bar.update(len(data))


class DeduplicateResult:
    def __init__(self):
        self.total_stined_file_count = 0
        self.total_stined_bytes = 0

        self.total_new_file_count = 0
        self.total_new_bytes = 0

        self.total_fast_backup = 0

    def add_new_file(self, size):
        self.total_new_file_count += 1
        self.total_new_bytes += size

    def add_stined_file(self, size):
        self.total_stined_file_count += 1
        self.total_stined_bytes += size

    def get_total_size(self):
        return self.total_new_bytes + self.total_stined_bytes


def add_dir_entry(backup_run, dir_entry_path, process_bar, result):
    """
    :param backup_run:
    :param dir_entry_path: filesystem_walk.DirEntryPath() instance
    :param process_bar:
    """
    # print(dir_entry_path.pformat())
    # print(dir_entry_path.stat.st_nlink)

    backup_entry = Path2(dir_entry_path.path)
    filesize = dir_entry_path.stat.st_size
    hash_filepath = Path2(f"{backup_entry.path}{os.extsep}{phlb_config.hash_name}")
    if hash_filepath.is_file():
        with hash_filepath.open("r") as hash_file:
            hash_hexdigest = hash_file.read().strip()
        if filesize > 0:
            process_bar.update(filesize)
    else:
        with hash_filepath.open("w") as hash_file:
            callback = HashCallback(process_bar)
            with backup_entry.open("rb") as f:
                hash = calculate_hash(f, callback)

            hash_hexdigest = hash.hexdigest()
            hash_file.write(hash_hexdigest)

    old_backup_entry = deduplicate(backup_entry, hash_hexdigest)
    if old_backup_entry is None:
        result.add_new_file(filesize)
    else:
        result.add_stined_file(filesize)

    BackupEntry.objects.create(
        backup_run, dir_entry_path.path_instance, hash_hexdigest=hash_hexdigest  # Path2() instance
    )


def add_dir_entries(backup_run, filtered_dir_entries, result):
    total_size = sum([entry.stat.st_size for entry in filtered_dir_entries])
    print("total size:", human_filesize(total_size))
    path_iterator = sorted(
        filtered_dir_entries,
        key=lambda x: x.stat.st_mtime,  # sort by last modify time
        reverse=True,  # sort from newest to oldes
    )
    # FIXME: The process bar will stuck if many small/null byte files are processed
    # Maybe: Change from bytes to file count and use a second bar if a big file
    # hash will be calculated.
    with tqdm(total=total_size, unit="B", unit_scale=True) as process_bar:
        for dir_entry in path_iterator:
            try:
                add_dir_entry(backup_run, dir_entry, process_bar, result)
            except Exception as err:
                # A unexpected error occurred.
                # Print and add traceback to summary
                log.error(f"Can't backup {dir_entry}: {err}")
                for line in exc_plus():
                    log.error(strip_ansi(line))


def add_backup_entries(backup_run, result):
    backup_path = backup_run.path_part()
    stats_helper = StatisticHelper()
    scandir_walk = ScandirWalker(
        top_path=backup_path,
        stats_helper=stats_helper,
        skip_dir_patterns=(),
        skip_file_patterns=(
            f"*.{phlb_config.hash_name}",  # skip all existing hash files
            BACKUP_RUN_CONFIG_FILENAME,  # skip phlb_config.ini
        ),
        verbose=True
    )
    filtered_dir_entries = [DirEntryPath(dir_entry) for dir_entry in scandir_walk]
    add_dir_entries(backup_run, filtered_dir_entries, result)


def add_backup_run(backup_run_path):
    print(f"*** add backup run: {backup_run_path.path}")

    backup_name = backup_run_path.parent.stem
    date_part = backup_run_path.stem
    try:
        backup_datetime = datetime.datetime.strptime(date_part, phlb_config.sub_dir_formatter)
    except ValueError as err:
        print(f"\nERROR parsing datetime from given path: {err}")
        print(" * Is the given path right?")
        print()
        return

    backup_run = BackupRun.objects.create(
        name=backup_name,
        backup_datetime=backup_datetime,
        completed=False)
    result = DeduplicateResult()
    add_backup_entries(backup_run, result)
    print(f"*** backup run {backup_name} - {date_part} added:")
    total_size = result.get_total_size()
    print(
        " * new content saved: %i files (%s %.1f%%)"
        % (
            result.total_new_file_count,
            human_filesize(result.total_new_bytes),
            to_percent(result.total_new_bytes, total_size),
        )
    )
    print(
        " * stint space via hardlinks: %i files (%s %.1f%%)"
        % (
            result.total_stined_file_count,
            human_filesize(result.total_stined_bytes),
            to_percent(result.total_stined_bytes, total_size),
        )
    )


def add_backup_name(backup_name_path):
    backup_runs = scandir_limited(backup_name_path.path, limit=1)
    for dir_entry in backup_runs:
        backup_run_path = Path2(dir_entry.path)
        print(f" * {backup_run_path.stem}")
        try:
            backup_run = BackupRun.objects.get_from_config_file(backup_run_path)
        except (FileNotFoundError, BackupRun.DoesNotExist) as err:
            print(f"Error: {err}")
            # no phlb_config.ini
            add_backup_run(backup_run_path)
        else:
            print("\tBackup exists:", backup_run)


def add_all_backups():
    abs_dst_root = Path2(phlb_config.backup_path)
    backup_names = scandir_limited(abs_dst_root.path, limit=1)
    for dir_entry in backup_names:
        backup_name_path = Path2(dir_entry.path)
        print("_" * 79)
        print(f"'{backup_name_path.stem}' (path: {backup_name_path.path})")
        add_backup_name(backup_name_path)
