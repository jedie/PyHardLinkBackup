import logging

from cli_base.cli_tools.shell_completion import setup_tyro_shell_completion
from cli_base.cli_tools.verbosity import setup_logging
from cli_base.tyro_commands import TyroVerbosityArgType
from rich import print  # noqa

from PyHardLinkBackup.cli_dev import app


logger = logging.getLogger(__name__)


@app.command
def shell_completion(verbosity: TyroVerbosityArgType = 1, remove: bool = False) -> None:
    """
    Setup shell completion for this CLI (Currently only for bash shell)
    """
    setup_logging(verbosity=verbosity)
    setup_tyro_shell_completion(
        prog_name='PyHardLinkBackup_dev_cli',
        remove=remove,
    )
