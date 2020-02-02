"""
    :copyleft: 2020 by PyHardLinkBackup team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""

from pathlib import Path

# https://github.com/jedie/PyHardLinkBackup
import pyhardlinkbackup
from pyhardlinkbackup import __version__

PACKAGE_ROOT = Path(pyhardlinkbackup.__file__).parent.parent


def assert_file_contains_string(file_path, string):
    with file_path.open('r') as f:
        for line in f:
            if string in line:
                return
    raise AssertionError(f'File {file_path} does not contain {string!r} !')


def test_version():
    if 'dev' not in __version__ and 'rc' not in __version__:
        version_string = f'v{__version__}'

        assert_file_contains_string(
            file_path=Path(PACKAGE_ROOT, 'README.creole'),
            string=version_string
        )

        assert_file_contains_string(
            file_path=Path(PACKAGE_ROOT, 'README.rst'),
            string=version_string
        )

    assert_file_contains_string(
        file_path=Path(PACKAGE_ROOT, 'pyproject.toml'),
        string=f'version = "{__version__}"'
    )
