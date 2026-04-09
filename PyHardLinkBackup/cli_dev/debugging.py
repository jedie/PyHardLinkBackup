import logging
from pathlib import Path

from cli_base.cli_tools.verbosity import setup_logging
from cli_base.tyro_commands import TyroVerbosityArgType
from rich import print  # noqa

from PyHardLinkBackup.cli_dev import app
from PyHardLinkBackup.utilities.filesystem import iter_scandir_files, verbose_path_stat
from PyHardLinkBackup.utilities.humanize import PrintTimingContextManager
from PyHardLinkBackup.utilities.tyro_cli_shared_args import (
    DEFAULT_EXCLUDE_DIRECTORIES,
    TyroExcludeDirectoriesArgType,
    TyroOneFileSystemArgType,
)


logger = logging.getLogger(__name__)


@app.command
def fs_info(
    path: Path,
    /,
    one_file_system: TyroOneFileSystemArgType = True,
    excludes: TyroExcludeDirectoriesArgType = DEFAULT_EXCLUDE_DIRECTORIES,
    verbosity: TyroVerbosityArgType = 2,
) -> None:
    """
    Display information about the filesystem under the given path.
    """
    setup_logging(verbosity=verbosity)
    exclude_set = set(excludes)

    src_path_stat = verbose_path_stat(path)
    src_device_id = src_path_stat.st_dev

    with PrintTimingContextManager('Filesystem scan completed in'):
        for entry in iter_scandir_files(
            path=path,
            one_file_system=one_file_system,
            src_device_id=src_device_id,
            excludes=exclude_set,
        ):
            entry_path = Path(entry.path)
            entry_stat = verbose_path_stat(entry_path)
            print(f'Size: {entry_stat.st_size} bytes, Inode: {entry_stat.st_ino}, File: {entry_path}')
