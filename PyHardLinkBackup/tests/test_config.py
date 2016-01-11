import os
import sys
import unittest

from click.testing import CliRunner

from PyHardLinkBackup.phlb.config import phlb_config

from PyHardLinkBackup.phlb_cli import cli


USER_INI=os.path.join(os.path.expanduser("~"), "PyHardLinkBackup.ini")


class TestConfig(unittest.TestCase):
    def setUp(self):
        phlb_config._load(force=True)

    def test_user_ini_default(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "--debug"])
        print(result.output)
        self.assertIn("PyHardLinkBackup", result.output)

        # First the unittest temp .ini will be used:
        ini_path=os.path.join(os.getcwd(), "PyHardLinkBackup.ini")
        self.assertIn(ini_path, result.output)

        self.assertIn("'database_name': ':memory:',", result.output)
        self.assertIn("'default_new_path_mode': 448,", result.output)
        self.assertIn("'hash_name': 'sha512',", result.output)
        self.assertEqual(result.exit_code,0)

        # go into a new temp dir, without a .ini:
        runner = CliRunner()
        with runner.isolated_filesystem():
            phlb_config._load(force=True)
            result = runner.invoke(cli, ["config", "--debug"])
            self.assertIn(USER_INI, result.output)
            self.assertIn("PyHardLinkBackups.sqlite3", result.output)


    def test_overwrite(self):
        """
        test if a .ini in current work dir will overwrite settings
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("PyHardLinkBackup.ini", 'w') as ini:
                ini.write("[foo]\nhash_name=md5")

            phlb_config._load(force=True)

            result = runner.invoke(cli, ["config", "--debug"])
            print(result.output)
            self.assertIn("PyHardLinkBackup", result.output)

            ini_path=os.path.join(os.getcwd(), "PyHardLinkBackup.ini")
            self.assertIn(ini_path, result.output)

            self.assertIn("'hash_name': 'md5',", result.output)
            self.assertEqual(result.exit_code,0)