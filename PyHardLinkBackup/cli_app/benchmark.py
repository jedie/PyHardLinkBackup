import logging
from pathlib import Path

from cli_base.cli_tools.verbosity import setup_logging
from cli_base.tyro_commands import TyroVerbosityArgType
from rich import print  # noqa

from PyHardLinkBackup.backup import backup_tree
from PyHardLinkBackup.cli_app import app


logger = logging.getLogger(__name__)


@app.command
def backup(
    src: Path,
    dst: Path,
    verbosity: TyroVerbosityArgType = 1,
) -> None:
    """
    Backup the source directory to the destination directory using hard links for deduplication.
    """
    setup_logging(verbosity=verbosity)
    backup_tree(src, dst)
