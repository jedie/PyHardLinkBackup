import os
import unittest
import pprint

import pathlib

import sys

from PyHardLinkBackup.tests.base import BaseCreatedTwoBackupsTestCase, BaseCreatedOneBackupsTestCase
from PyHardLinkBackup.tests.utils import UnittestFileSystemHelper


class TestTwoBackups(BaseCreatedTwoBackupsTestCase):
    def test_changed_file(self):
        filepath = os.path.join(self.source_path, "sub dir A", "dir_A_file_B.txt")
        with open(filepath, "w") as f:
            f.write(">>> The new content! <<<")

        # run backup
        result = self.invoke_cli("backup", self.source_path)

        print(result.output)

        self.assertIn("110 Bytes in 5 files to backup.", result.output)
        self.assertIn("new content to saved: 1 files (24 Bytes 21.8%)", result.output)
        self.assertIn("stint space via hardlinks: 4 files (86 Bytes 78.2%)", result.output)

        self.assert_backup_fs_count(3) # there are tree backups in filesystem
        backup_path = self.get_newest_backup_path()

        fs_helper = UnittestFileSystemHelper()
        #fs_helper.print_tree(self.backup_path)
        tree_list = fs_helper.pformat_tree(backup_path, with_timestamps=False)
        pprint.pprint(tree_list,indent=0, width=200)
        self.assertListEqual(tree_list, [
            backup_path,
            'root_file_A.txt                L - The root file A content.',
            'root_file_A.txt.sha512         F - 13e3e...d7df6',
            'root_file_B.txt                L - The root file B content.',
            'root_file_B.txt.sha512         F - 4bb47...5a181',
            'sub dir A                      D',
            'sub dir A/dir_A_file_A.txt     L - File A in sub dir A.',
            'sub dir A/dir_A_file_A.txt.sha512 F - 89091...f8669',
            'sub dir A/dir_A_file_B.txt     F - >>> The new content! <<<', # <<-- new file
            'sub dir A/dir_A_file_B.txt.sha512 F - b7203...eb68f', # <<-- new hash
            'sub dir B                      D',
            'sub dir B/sub_file.txt         L - File in sub dir B.',
            'sub dir B/sub_file.txt.sha512  F - bbe59...dbdbb'
        ])

        # first + second data must be untouched:
        self.assert_first_backup()
        self.assert_second_backup()


class TestOneBackups(BaseCreatedOneBackupsTestCase):
    def test_summary(self):
        summary_filepath = pathlib.Path(self.first_run_path + " summary.txt")
        self.assertTrue(summary_filepath.is_file(), "%s doesn't exist" % summary_filepath)

        with summary_filepath.open("r") as f: # Path().read_text() is new in Py 2.5
            summary_content = f.read()
        print(summary_content)

        self.assertIn("Backup done:", summary_content)
        self.assertIn("Source file sizes: 106 Bytes", summary_content)
        self.assertIn("new content to saved: 5 files (106 Bytes 100.0%)", summary_content)
        self.assertIn("stint space via hardlinks: 0 files (0 Bytes 0.0%)", summary_content)


    def test_log_file(self):
        log_content = self.get_log_content(self.first_run_log)

        print(log_content)
        self.assertIn("Backup", log_content)
        self.assertIn("Start low level logging", log_content)

    @unittest.skipIf(sys.platform.startswith("win"), "TODO: work-a-round for os.chmod()")
    def test_skip_files(self):
        """
        Test if not open able source files, will be skipped
        and the backup will save the other files.
        """
        filepath1 = os.path.join(self.source_path, "root_file_B.txt")
        filepath2 = os.path.join(self.source_path, "sub dir B", "sub_file.txt")

        os.chmod(filepath1, 0o000)
        os.chmod(filepath2, 0o000)

        result = self.invoke_cli("backup", self.source_path)
        print(result.output)

        self.assertIn("106 Bytes in 5 files to backup.", result.output)
        self.assertIn("WARNING: Skipped 2 files", result.output)
        self.assertIn("new content to saved: 0 files (0 Bytes 0.0%)", result.output)
        self.assertIn("stint space via hardlinks: 3 files (64 Bytes 60.4%)", result.output)

        self.assertEqual(os.listdir(self.backup_path), ["source unittests files"])
        self.assert_backup_fs_count(2)

        log_content = self.get_log_content(self.first_run_log)
        print(log_content)
        self.assertIn("Skip file", log_content)
        self.assertIn("/root_file_B.txt error:", log_content)
        self.assertIn("/sub dir B/sub_file.txt error:", log_content)
