import os

from django_tools.unittest_utils.assertments import assert_pformat_equal

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.backup_app.models import BackupEntry, BackupRun
from pyhardlinkbackup.phlb.config import phlb_config
from pyhardlinkbackup.tests.base import (
    BaseCreatedOneBackupsTestCase,
    BaseCreatedTwoBackupsTestCase,
    BaseTestCase,
    BaseWithSourceFilesTestCase
)
from pyhardlinkbackup.tests.utils import UnittestFileSystemHelper


class TestUnittestSetup(BaseTestCase):
    def test_ini_created(self):
        self.assertTrue(os.path.isfile(self.ini_path))

    def test_unittests_settings_active(self):
        assert_pformat_equal(phlb_config.database_name, ":memory:")
        assert_pformat_equal(phlb_config.sub_dir_formatter, "%Y-%m-%d-%H%M%S-%f")

    def test_db_empty(self):
        assert_pformat_equal(BackupRun.objects.all().count(), 0)
        assert_pformat_equal(BackupEntry.objects.all().count(), 0)


class TestBaseBackup(BaseWithSourceFilesTestCase):
    def test_created_source_files(self):
        """
        Check if the test source files are created

        mtime = 111111111 # 1973-07-10 01:11:51
        """
        fs_helper = UnittestFileSystemHelper()
        tree_list = fs_helper.pformat_tree(self.source_path, with_timestamps=True)
        # pprint.pprint(tree_list,indent=0, width=200)
        self.assertListEqual(
            tree_list,
            [
                self.source_path,
                "root_file_A.txt                F 19730710:001151 - The root file A content.",
                "root_file_B.txt                F 19730710:001152 - The root file B content.",
                "sub dir A                      D 19730710:001155",
                "sub dir A/dir_A_file_A.txt     F 19730710:001153 - File A in sub dir A.",
                "sub dir A/dir_A_file_B.txt     F 19730710:001154 - File B in sub dir A.",
                "sub dir B                      D 19730710:001157",
                "sub dir B/sub_file.txt         F 19730710:001156 - File in sub dir B.",
            ],
        )


class TestBaseCreatedOneBackupsTestCase(BaseCreatedOneBackupsTestCase):
    def test_first_backup_run(self):
        self.assert_click_exception(self.first_backup_result)

        output = self.first_backup_result.output

        print(self.first_backup_result.output)

        assert "pyhardlinkbackup" in output

        assert "* 0 directories skipped." in output
        assert "* 0 files skipped." in output
        assert "* Files to backup: 5 files" in output
        assert "* Source file sizes: 106 Bytes" in output
        assert "* fast backup: 0 files" in output
        assert "* new content saved: 5 files (106 Bytes 100.0%)" in output
        assert "* stint space via hardlinks: 0 files (0 Bytes 0.0%)" in output

        assert_pformat_equal(os.listdir(self.backup_path), ["source unittests files"])
        self.assert_backup_fs_count(1)

        assert self.first_run_path in output

        self.assert_first_backup()

    def test_database_entries(self):
        """
        Check models.BackupEntry
         * assert all entries exist in filesystem
         * assert entry count

        Here we have 5 files in one backup run
        """
        assert_pformat_equal(BackupRun.objects.all().count(), 1)
        self.assert_database_backup_entries(count=5)


class TestBaseCreatedTwoBackupsTestCase(BaseCreatedTwoBackupsTestCase):
    def test_first_backup_run(self):
        """
        After a 2nd backup exist all files are hardlinks!
        """
        self.assert_backuped_files(self.first_run_path, backup_run_pk=1)

    def test_second_backup_run(self):
        self.assert_click_exception(self.second_backup_result)
        print(self.second_backup_result.output)

        self.assertIn("106 Bytes in 5 files to backup.", self.second_backup_result.output)
        self.assertNotIn("WARNING: Omitted", self.second_backup_result.output)
        self.assertIn(" * fast backup: 5 files", self.second_backup_result.output)
        self.assertIn(" * new content saved: 0 files (0 Bytes 0.0%)", self.second_backup_result.output)
        self.assertIn(
            "stint space via hardlinks: 5 files (106 Bytes 100.0%)",
            self.second_backup_result.output)

        assert_pformat_equal(os.listdir(self.backup_path), ["source unittests files"])
        self.assert_backup_fs_count(2)

        self.assertIn(self.second_run_path, self.second_backup_result.output)

        self.assert_second_backup()

    def test_database_entries(self):
        """
        Check models.BackupEntry
         * assert all entries exist in filesystem
         * assert entry count

        Here we have 5 files in two backup runs
        """
        assert_pformat_equal(BackupRun.objects.all().count(), 2)
        self.assert_database_backup_entries(count=10)
