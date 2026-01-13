import logging
from pathlib import Path
from typing import Annotated

import tyro
from cli_base.cli_tools.verbosity import setup_logging
from cli_base.tyro_commands import TyroVerbosityArgType
from rich import print  # noqa

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
