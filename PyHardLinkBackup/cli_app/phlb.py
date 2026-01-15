import logging
from pathlib import Path
from typing import Annotated

import tyro
from cli_base.cli_tools.verbosity import setup_logging
from cli_base.tyro_commands import TyroVerbosityArgType
from rich import print  # noqa

from PyHardLinkBackup import rebuild_databases
from PyHardLinkBackup.backup import backup_tree
from PyHardLinkBackup.cli_app import app


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
    excludes: Annotated[
        tuple,
        tyro.conf.arg(
            help='List of directory or file names to exclude from backup.',
        ),
    ] = ('__pycache__', '.cache', '.temp', '.tmp', '.tox', '.nox'),
    verbosity: TyroVerbosityArgType = 2,
) -> None:
    """
    Backup the source directory to the destination directory using hard links for deduplication.
    """
    setup_logging(verbosity=verbosity)
    backup_tree(
        src_root=src,
        backup_root=dst,
        excludes=set(excludes),
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
    verbosity: TyroVerbosityArgType = 2,
) -> None:
    """
    Rebuild the file hash and size database by scanning all backup files.
    Note: It will not verify with existing file hashes/sizes,
    it just adds missing hashes/sizes db entries used for deduplication.
    """
    setup_logging(verbosity=verbosity)
    rebuild_databases.rebuild(backup_root=backup_root)
