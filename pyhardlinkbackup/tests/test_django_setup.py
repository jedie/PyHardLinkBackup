import os
import shutil
import subprocess
from pathlib import Path

# https://github.com/jedie/PyHardLinkBackup
import pyhardlinkbackup

ROOT_PATH = Path(pyhardlinkbackup.__file__).parent.parent


def get_manage_py_path():
    manage_path = shutil.which('manage')
    return manage_path


def test_manage_help():
    """
    Run './manage.py --help' via subprocess and check output.
    """
    output = subprocess.check_output(
        [get_manage_py_path(), '--help'],
        universal_newlines=True,
        env=os.environ,
        stderr=subprocess.STDOUT,
        cwd=str(ROOT_PATH),
    )
    print(output)
    assert 'ERROR' not in output
    assert '[django]' in output
    assert '[backup_app]' in output
    assert ' add\n' in output


def test_manage_check():
    output = subprocess.check_output(
        [get_manage_py_path(), 'check'],
        universal_newlines=True,
        env=os.environ,
        stderr=subprocess.STDOUT,
        cwd=str(ROOT_PATH),
    )
    print(output)
    assert 'System check identified no issues' in output


def test_missing_migrations():
    output = subprocess.check_output(
        [get_manage_py_path(), 'makemigrations', '--dry-run'],
        universal_newlines=True,
        env=os.environ,
        stderr=subprocess.STDOUT,
        cwd=str(ROOT_PATH),
    )
    print(output)
    assert 'No changes detected' in output
