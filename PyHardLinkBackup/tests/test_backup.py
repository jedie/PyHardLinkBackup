import os
import pprint

from PyHardLinkBackup.tests.base import BaseCreatedTwoBackupsTestCase
from PyHardLinkBackup.tests.utils import UnittestFileSystemHelper


class TestBackup(BaseCreatedTwoBackupsTestCase):
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
        self.assertEqual(tree_list, [
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