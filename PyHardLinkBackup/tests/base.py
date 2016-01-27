import configparser
import logging
import shutil
import os
import unittest
import tempfile

# Use the built-in version of scandir/walk if possible, otherwise
# use the scandir module version
import pathlib

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


def get_newest_directory(path):
    """
    Returns the newest directory path by mtime_ns
    """
    sub_dirs = [entry for entry in scandir(path) if entry.is_dir()]
    sub_dirs.sort(key=lambda x: x.stat().st_mtime_ns)
    print("Backup sub dirs:\n\t%s" % "\n\t".join([p.path for p in sub_dirs]))
    sub_dir = sub_dirs[-1]
    return sub_dir.path


class BaseTestCase(django.test.TestCase):
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

        self.temp_root_path=tempfile.mkdtemp()
        self.backup_path = os.path.join(self.temp_root_path, "PyHardLinkBackups")
        self.ini_path = os.path.join(self.temp_root_path, "PyHardLinkBackup.ini")

        os.chdir(self.temp_root_path)

        # set_phlb_logger(logging.DEBUG)

        self.set_ini_values(self.ini_path,
            debug=True, # print debug info about created .ini

            # Use SQLite ':memory:' database in all tests:
            DATABASE_NAME= ":memory:",

            # add microsecond to formatter
            # Important for test, so that every run will create a new directory
            SUB_DIR_FORMATTER= "%Y-%m-%d-%H%M%S.%f",

            BACKUP_PATH=self.backup_path
        )

    def tearDown(self):
        # FIXME: Under windows the root temp dir can't be deleted:
        # PermissionError: [WinError 32] The process cannot access the file because it is being used by another process
        def rmtree_error(function, path, excinfo):
            print("Error remove temp: %r" % path)
        shutil.rmtree(self.temp_root_path, ignore_errors=True, onerror=rmtree_error)

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

    def get_log_content(self, log_filepath):
        self.assertTrue(log_filepath.is_file(), "%s doesn't exist" % log_filepath)

        with log_filepath.open("r") as f: # Path().read_text() is new in Py 2.5
            return f.read()

    def assert_backup_fs_count(self, count):
        # TODO: count dirs and files seperate!
        fs_items=os.listdir(self.backup_sub_path)

        # add .log and summay files for every backup run
        count += (count * 2)

        self.assertEqual(len(fs_items), count, "%i != %i - items: %s" % (len(fs_items), count, repr(fs_items)))


class BaseWithSourceFilesTestCase(BaseSourceDirTestCase):
    """
    Tests with created example source files under /temp/source unittests files&
    """
    def setUp(self):
        super(BaseWithSourceFilesTestCase, self).setUp()

        fs_helper = UnittestFileSystemHelper()
        fs_helper.create_test_fs(EXAMPLE_FS_DATA, self.source_path)


class BaseCreatedOneBackupsTestCase(BaseWithSourceFilesTestCase):
    """
    Test that used existing backups:
    The 'source unittests files' will be backuped one time.
    """
    def assert_first_backup(self):
        fs_helper = UnittestFileSystemHelper()
        #fs_helper.print_tree(self.backup_path)
        tree_list = fs_helper.pformat_tree(self.first_run_path, with_timestamps=False)
        #print("\n".join(tree_list))
        # pprint.pprint(tree_list,indent=0, width=200)
        self.assertListEqual(tree_list, [
            self.first_run_path,
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
        ])


    def setUp(self):
        super(BaseCreatedOneBackupsTestCase, self).setUp()

        self.first_backup_result = self.invoke_cli("backup", self.source_path)
        self.first_run_path = self.get_newest_backup_path()

        self.first_run_log = pathlib.Path(self.first_run_path + ".log")


class BaseCreatedTwoBackupsTestCase(BaseCreatedOneBackupsTestCase):
    """
    Test that used existing backups:
    The 'source unittests files' will be backuped two times.

    Note:
        After a second backup run, all files (incl. first run files)
        will be 'display' as filesystem type 'L' (link).
        Because: 'if stat.st_nlink > 1:' will be True
    """
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
        super(BaseCreatedTwoBackupsTestCase, self).setUp()

        self.second_backup_result = self.invoke_cli("backup", self.source_path)
        self.second_run_path = self.get_newest_backup_path()

    def assert_first_backup(self):
        fs_helper = UnittestFileSystemHelper()
        tree_list = fs_helper.pformat_tree(self.first_run_path, with_timestamps=False)
        #print("\n".join(tree_list))
        # pprint.pprint(tree_list,indent=0, width=200)
        self.assertListEqual(tree_list, [self.first_run_path]+self.backuped_file_info)

    def assert_second_backup(self):
        fs_helper = UnittestFileSystemHelper()
        tree_list = fs_helper.pformat_tree(self.second_run_path, with_timestamps=False)
        #print("\n".join(tree_list))
        # pprint.pprint(tree_list,indent=0, width=200)
        self.assertListEqual(tree_list, [self.second_run_path]+self.backuped_file_info)
