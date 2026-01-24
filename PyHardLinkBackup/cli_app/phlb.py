import logging
from pathlib import Path
from typing import Annotated

import tyro
from rich import print  # noqa

from PyHardLinkBackup import compare_backup, rebuild_databases
from PyHardLinkBackup.backup import backup_tree
from PyHardLinkBackup.cli_app import app
from PyHardLinkBackup.logging_setup import (
    DEFAULT_CONSOLE_LOG_LEVEL,
    DEFAULT_LOG_FILE_LEVEL,
    LoggingManager,
    TyroConsoleLogLevelArgType,
    TyroLogFileLevelArgType,
)
from PyHardLinkBackup.utilities.tyro_cli_shared_args import (
    DEFAULT_EXCLUDE_DIRECTORIES,
    TyroBackupNameArgType,
    TyroExcludeDirectoriesArgType,
    TyroOneFileSystemArgType,
)


logger = logging.getLogger(__name__)


@app.command
def backup(
    src: Annotated[
        Path,
        tyro.conf.arg(
            metavar='source',
            help='Source directory to back up.',
        ),
    ],
    dst: Annotated[
        Path,
        tyro.conf.arg(
            metavar='destination',
            help='Destination directory for the backup.',
        ),
    ],
    /,
    name: TyroBackupNameArgType = None,
    one_file_system: TyroOneFileSystemArgType = True,
    excludes: TyroExcludeDirectoriesArgType = DEFAULT_EXCLUDE_DIRECTORIES,
    verbosity: TyroConsoleLogLevelArgType = DEFAULT_CONSOLE_LOG_LEVEL,
    log_file_level: TyroLogFileLevelArgType = DEFAULT_LOG_FILE_LEVEL,
) -> None:
    """
    Backup the source directory to the destination directory using hard links for deduplication.
    """
    log_manager = LoggingManager(
        console_level=verbosity,
        file_level=log_file_level,
    )
    backup_tree(
        src_root=src,
        backup_root=dst,
        backup_name=name,
        one_file_system=one_file_system,
        excludes=excludes,
        log_manager=log_manager,
    )


@app.command
def compare(
    src: Annotated[
        Path,
        tyro.conf.arg(
            metavar='source',
            help='Source directory that should be compared with the last backup.',
        ),
    ],
    dst: Annotated[
        Path,
        tyro.conf.arg(
            metavar='destination',
            help='Destination directory with the backups. Will pick the last backup for comparison.',
        ),
    ],
    /,
    one_file_system: TyroOneFileSystemArgType = True,
    excludes: TyroExcludeDirectoriesArgType = DEFAULT_EXCLUDE_DIRECTORIES,
    verbosity: TyroConsoleLogLevelArgType = DEFAULT_CONSOLE_LOG_LEVEL,
    log_file_level: TyroLogFileLevelArgType = DEFAULT_LOG_FILE_LEVEL,
) -> None:
    """
    Compares a source tree with the last backup and validates all known file hashes.
    """
    log_manager = LoggingManager(
        console_level=verbosity,
        file_level=log_file_level,
    )
    compare_backup.compare_tree(
        src_root=src,
        backup_root=dst,
        one_file_system=one_file_system,
        excludes=excludes,
        log_manager=log_manager,
    )


@app.command
def rebuild(
    backup_root: Annotated[
        Path,
        tyro.conf.arg(
            metavar='backup-directory',
            help='Root directory of the the backups.',
        ),
    ],
    /,
    skip_same_inode: Annotated[
        bool,
        tyro.conf.arg(help='Skip files that have the same inode number as already processed files.'),
    ] = True,
    verbosity: TyroConsoleLogLevelArgType = DEFAULT_CONSOLE_LOG_LEVEL,
    log_file_level: TyroLogFileLevelArgType = DEFAULT_LOG_FILE_LEVEL,
) -> None:
    """
    Rebuild the file hash and size database by scanning all backup files. And also verify SHA256SUMS
    and/or store missing hashes in SHA256SUMS files.
    """
    log_manager = LoggingManager(
        console_level=verbosity,
        file_level=log_file_level,
    )
    rebuild_databases.rebuild(
        backup_root=backup_root,
        skip_same_inode=skip_same_inode,
        log_manager=log_manager,
    )
