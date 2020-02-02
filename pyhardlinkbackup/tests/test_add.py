import pathlib
import shutil

from click.testing import CliRunner

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.phlb import BACKUP_RUN_CONFIG_FILENAME
from pyhardlinkbackup.phlb_cli import cli
from pyhardlinkbackup.tests.base import BaseCreatedOneBackupsTestCase


class TestOneBackups(BaseCreatedOneBackupsTestCase):
    def _copy_first_backup(self, remove_old_config=True):
        new_path = pathlib.Path(
            # First commit date ;)
            pathlib.Path(self.first_run_path).parent, "2015-12-29-000015-000000"
        )
        shutil.copytree(self.first_run_path, str(new_path))

        if remove_old_config:
            config_path = pathlib.Path(new_path, BACKUP_RUN_CONFIG_FILENAME)
            config_path.unlink()

        return new_path

    def test_wrong_config(self):
        """
        Test what happen, if the phlb_config.ini pointed to a other BackupRun entry.
        """
        self._copy_first_backup(remove_old_config=False)

        runner = CliRunner()
        result = runner.invoke(cli, args=["add"])
        print(result.output)

        assert_msg = str(result.exception)
        self.assertIn("Backup path mismatch", assert_msg)
        self.assertIn(str(pathlib.Path("2015-12-29-000015-000000",
                                       BACKUP_RUN_CONFIG_FILENAME)), assert_msg)

    def test_add(self):
        self.assert_first_backup()

        self._copy_first_backup(remove_old_config=True)

        self.assert_database_backup_entries(count=5)

        result = self.invoke_cli("add")
        print(result.output)

        self.assertIn(" * new content saved: 0 files (0 Bytes 0.0%)", result.output)
        self.assertIn(" * stint space via hardlinks: 5 files (106 Bytes 100.0%)", result.output)

        self.assert_database_backup_entries(count=10)

        # Just run a second time:
        result = self.invoke_cli("add")
        print("*" * 79)
        print(result.output)

        self.assertIn("Backup exists", result.output)

        self.assertNotIn("scan/filter source directory", result.output)
        self.assertNotIn("total size", result.output)
        self.assertNotIn("new content saved", result.output)

        self.assert_database_backup_entries(count=10)
