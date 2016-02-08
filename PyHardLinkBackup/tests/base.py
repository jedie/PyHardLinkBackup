import configparser
import logging
import shutil
import os
import pathlib
import sys
import tempfile
import unittest

# Use the built-in version of scandir/walk if possible, otherwise
# use the scandir module version
try:
    from os import scandir # new in Python 3.5
except ImportError:
    # use https://pypi.python.org/pypi/scandir
    try:
        from scandir import scandir
    except ImportError:
        raise ImportError("For Python <2.5: Please install 'scandir' !")

import django

from click.testing import CliRunner

from PyHardLinkBackup.backup_app.models import BackupEntry
from PyHardLinkBackup.phlb.config import phlb_config
from PyHardLinkBackup.phlb_cli import cli
from PyHardLinkBackup.tests.utils import UnittestFileSystemHelper
from PyHardLinkBackup.phlb.phlb_main import FileBackup

log = logging.getLogger("phlb.%s" % __name__)


def get_newest_directory(path):
    """
    Returns the newest directory path by mtime_ns
    """
    sub_dirs = [entry for entry in scandir(path) if entry.is_dir()]
    sub_dirs.sort(key=lambda x: x.stat().st_mtime_ns)
    print("Backup sub dirs:\n\t%s" % "\n\t".join([p.path for p in sub_dirs]))
    sub_dir = sub_dirs[-1]
    return sub_dir.path

class BaseTempTestCase(unittest.TestCase):
    """
    Test case with a temporary directory
    """
    def setUp(self):
        super(BaseTempTestCase, self).setUp()
        self.temp_root_path=tempfile.mkdtemp(prefix="%s_" % __name__)
        os.chdir(self.temp_root_path)

    def tearDown(self):
        super(BaseTempTestCase, self).tearDown()
        # FIXME: Under windows the root temp dir can't be deleted:
        # PermissionError: [WinError 32] The process cannot access the file because it is being used by another process
        def rmtree_error(function, path, excinfo):
            log.error("\nError remove temp: %r\n%s", path, excinfo[1])
        shutil.rmtree(self.temp_root_path, ignore_errors=True, onerror=rmtree_error)


class BaseTestCase(BaseTempTestCase, django.test.TestCase):
    def set_ini_values(self, filepath, debug=False, **ini_extras):
        config = configparser.RawConfigParser()
        config["unittests"]=ini_extras
        with open(filepath, 'w') as ini:
            config.write(ini)
        print("%r for unittests created." % filepath)

        if debug:
            with open(filepath, 'r') as ini:
                print("+"*79)
                print(ini.read())
                print("+"*79)

        phlb_config._load(force=True)

    def setUp(self):
        super(BaseTestCase, self).setUp()
        self.backup_path = os.path.join(self.temp_root_path, "PyHardLinkBackups")
        self.ini_path = os.path.join(self.temp_root_path, "PyHardLinkBackup.ini")

        # set_phlb_logger(logging.DEBUG)

        self.set_ini_values(self.ini_path,
            debug=True, # print debug info about created .ini

            # Use SQLite ':memory:' database in all tests:
            DATABASE_NAME= ":memory:",

            # add microsecond to formatter
            # Important for test, so that every run will create a new directory
            SUB_DIR_FORMATTER= "%Y-%m-%d-%H%M%S-%f",

            BACKUP_PATH=self.backup_path
        )

    def tearDown(self):
        super(BaseTestCase, self).tearDown()
        FileBackup._SIMULATE_SLOW_SPEED=False # disable it

    def simulate_slow_speed(self, sec):
        FileBackup._SIMULATE_SLOW_SPEED=sec

    def assert_click_exception(self, result):
        if result.exception:
            print("_"*79)
            print("Exception while running:")
            print(result.output)
            print("*"*79)
            raise result.exception

    def invoke_cli(self, *args):
        runner = CliRunner()
        result = runner.invoke(cli, args)
        self.assert_click_exception(result)
        return result

    def assert_database_backup_entries(self, count):
        queryset = BackupEntry.objects.all()
        for entry in queryset:
            path = entry.get_backup_path() # Path2() instance
            self.assertTrue(os.path.isfile(path.path), "File not found: %r" % path)

        self.assertEqual(queryset.count(), count)

    def assert_mtime_ns(self, mtime_ns1, mtime_ns2):
        if sys.platform.startswith("win"):
            # seems that windows/NTFS is less precise ;)
            # set the last two digits to null
            mtime_ns1 = int(mtime_ns1/100)*100
            mtime_ns2 = int(mtime_ns2/100)*100

        self.assertEqual(mtime_ns1, mtime_ns2)

    def assert_file_mtime_ns(self, filepath, mtime_ns):
        file_mtime_ns = os.stat(str(filepath)).st_mtime_ns
        self.assert_mtime_ns(file_mtime_ns, mtime_ns)


EXAMPLE_FS_DATA = {
    "root_file_A.txt": "The root file A content.",
    "root_file_B.txt": "The root file B content.",
    "sub dir A": {
        "dir_A_file_A.txt": "File A in sub dir A.",
        "dir_A_file_B.txt": "File B in sub dir A.",
    },
    "sub dir B": {
        "sub_file.txt": "File in sub dir B.",
    }
}


class BaseSourceDirTestCase(BaseTestCase):
    """
    Tests with empty "source unittests files" directory under /temp/
    """
    maxDiff=10000

    def setUp(self):
        super(BaseSourceDirTestCase, self).setUp()

        # directory to store source test files
        self.source_path = os.path.join(self.temp_root_path, "source unittests files")
        os.mkdir(self.source_path)

        # path to the backups for self.source_path
        self.backup_sub_path=os.path.join(self.backup_path, "source unittests files")

    def get_newest_backup_path(self):
        return get_newest_directory(self.backup_sub_path)

    #--------------------------------------------------------------------------

    def get_newest_log_filepath(self):
        run_path = self.get_newest_backup_path()
        return pathlib.Path(run_path + ".log")

    def get_log_content(self, log_filepath):
        self.assertTrue(log_filepath.is_file(), "%s doesn't exist" % log_filepath)
        with log_filepath.open("r") as f: # Path().read_text() is new in Py 2.5
            return f.read()

    def get_last_log_content(self):
        newest_log_filepath = self.get_newest_log_filepath()
        return self.get_log_content(newest_log_filepath)

    #--------------------------------------------------------------------------

    def get_newest_summary_filepath(self):
        run_path = self.get_newest_backup_path()
        return pathlib.Path(run_path + " summary.txt")

    def get_summary_content(self, summary_filepath):
        self.assertTrue(summary_filepath.is_file(), "%s doesn't exist" % summary_filepath)
        with summary_filepath.open("r") as f: # Path().read_text() is new in Py 2.5
            return f.read()

    def get_last_summary_content(self):
        newest_summary_filepath = self.get_newest_summary_filepath()
        return self.get_summary_content(newest_summary_filepath)

    #--------------------------------------------------------------------------

    def assert_backup_fs_count(self, count):
        files = []
        dirs = []
        for item in scandir(self.backup_sub_path):
            if item.is_file(follow_symlinks=False):
                files.append(item)
            if item.is_dir(follow_symlinks=False):
                dirs.append(item)

        self.assertEqual(len(dirs), count, "dir count: %i != %i - items: %s" % (
            len(dirs), count, repr(dirs))
        )

        # .log and summay files for every backup run
        file_count = count * 2
        self.assertEqual(len(files), file_count, "files count: %i != %i - items:\n%s" % (
            len(files), file_count, "\n".join([repr(f) for f in files]))
        )


class BaseWithSourceFilesTestCase(BaseSourceDirTestCase):
    """
    Tests with created example source files under /temp/source unittests files&
    """
    phlb_config_info=(
        'phlb_config.ini                F - [BACKUP_RUN]\nprimary_key = %i\n\n'
    )

    # on first run, all files are normal files and not links:
    first_backuped_file_info=[
        'root_file_A.txt                F - The root file A content.',
        'root_file_A.txt.sha512         F - 13e3e...d7df6',
        'root_file_B.txt                F - The root file B content.',
        'root_file_B.txt.sha512         F - 4bb47...5a181',
        'sub dir A                      D',
        'sub dir A/dir_A_file_A.txt     F - File A in sub dir A.',
        'sub dir A/dir_A_file_A.txt.sha512 F - 89091...f8669',
        'sub dir A/dir_A_file_B.txt     F - File B in sub dir A.',
        'sub dir A/dir_A_file_B.txt.sha512 F - b358d...b5b98',
        'sub dir B                      D',
        'sub dir B/sub_file.txt         F - File in sub dir B.',
        'sub dir B/sub_file.txt.sha512  F - bbe59...dbdbb'
    ]
    # after first run, all files are links:
    backuped_file_info=[
        'root_file_A.txt                L - The root file A content.',
        'root_file_A.txt.sha512         F - 13e3e...d7df6',
        'root_file_B.txt                L - The root file B content.',
        'root_file_B.txt.sha512         F - 4bb47...5a181',
        'sub dir A                      D',
        'sub dir A/dir_A_file_A.txt     L - File A in sub dir A.',
        'sub dir A/dir_A_file_A.txt.sha512 F - 89091...f8669',
        'sub dir A/dir_A_file_B.txt     L - File B in sub dir A.',
        'sub dir A/dir_A_file_B.txt.sha512 F - b358d...b5b98',
        'sub dir B                      D',
        'sub dir B/sub_file.txt         L - File in sub dir B.',
        'sub dir B/sub_file.txt.sha512  F - bbe59...dbdbb'
    ]

    def setUp(self):
        super(BaseWithSourceFilesTestCase, self).setUp()
        fs_helper = UnittestFileSystemHelper()
        fs_helper.create_test_fs(EXAMPLE_FS_DATA, self.source_path)

    def assert_first_backuped_files(self, backup_path):
        """
        all files are normal files and not hardlinks
        """
        fs_helper = UnittestFileSystemHelper()
        #fs_helper.print_tree(self.backup_path)
        tree_list = fs_helper.pformat_tree(backup_path, with_timestamps=False)
        #print("\n".join(tree_list))
        # pprint.pprint(tree_list,indent=0, width=200)

        file_infos = [
            backup_path,
            self.phlb_config_info % 1,
        ] + self.first_backuped_file_info
        self.assertListEqual(tree_list, file_infos)

    def assert_backuped_files(self, backup_path, backup_run_pk):
        """
        all files are hardlinks
        """
        fs_helper = UnittestFileSystemHelper()
        #fs_helper.print_tree(self.backup_path)
        tree_list = fs_helper.pformat_tree(backup_path, with_timestamps=False)
        #print("\n".join(tree_list))
        # pprint.pprint(tree_list,indent=0, width=200)

        file_info = [
            backup_path,
            self.phlb_config_info % backup_run_pk,
        ] + self.backuped_file_info
        self.assertListEqual(tree_list, file_info)

class BaseCreatedOneBackupsTestCase(BaseWithSourceFilesTestCase):
    """
    Test that used existing backups:
    The 'source unittests files' will be backuped one time.
    """
    def setUp(self):
        super(BaseCreatedOneBackupsTestCase, self).setUp()

        self.first_backup_result = self.invoke_cli("backup", self.source_path)
        self.first_run_path = self.get_newest_backup_path()

        self.first_run_log = pathlib.Path(self.first_run_path + ".log")

    def assert_first_backup(self):
        self.assert_first_backuped_files(self.first_run_path)


class BaseCreatedTwoBackupsTestCase(BaseCreatedOneBackupsTestCase):
    """
    Test that used existing backups:
    The 'source unittests files' will be backuped two times.

    Note:
        After a second backup run, all files (incl. first run files)
        will be 'display' as filesystem type 'L' (link).
        Because: 'if stat.st_nlink > 1:' will be True
    """
    def setUp(self):
        super(BaseCreatedTwoBackupsTestCase, self).setUp()

        self.second_backup_result = self.invoke_cli("backup", self.source_path)
        self.second_run_path = self.get_newest_backup_path()

    def assert_first_backup(self):
        """
        After a 2nd backup exist all files are hardlinks!
        """
        self.assert_backuped_files(self.first_run_path, backup_run_pk=1)

    def assert_second_backup(self):
        self.assert_backuped_files(self.second_run_path, backup_run_pk=2)
