from typing import Annotated

import tyro


TyroExcludeDirectoriesArgType = Annotated[
    tuple[str, ...],
    tyro.conf.arg(
        help='List of directories to exclude from backup.',
    ),
]
DEFAULT_EXCLUDE_DIRECTORIES = ('__pycache__', '.cache', '.temp', '.tmp', '.tox', '.nox')

TyroOneFileSystemArgType = Annotated[
    bool,
    tyro.conf.arg(
        help='Do not cross filesystem boundaries.',
    ),
]

TyroBackupNameArgType = Annotated[
    str | None,
    tyro.conf.arg(
        help=(
            'Optional name for the backup (used to create a subdirectory in the backup destination).'
            ' If not provided, the name of the source directory is used.'
        ),
    ),
]
