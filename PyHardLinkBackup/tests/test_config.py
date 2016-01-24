import os
import sys
import unittest

from django.conf import settings

from click.testing import CliRunner

from PyHardLinkBackup.phlb.config import phlb_config

from PyHardLinkBackup.phlb_cli import cli
from PyHardLinkBackup.tests.base import BaseTestCase


USER_INI_PATH=os.path.join(os.path.expanduser("~"), "PyHardLinkBackup.ini")

class TestConfig(BaseTestCase):

    def test_test_database(self):
        current_name=settings.DATABASES['default']['NAME']
        self.assertIn("memory", current_name)

    def test_user_ini_default(self):
        runner = CliRunner()
        result = self.invoke_cli("config", "--debug")
        self.assertIn("PyHardLinkBackup", result.output)

        # check if unittest temp PyHardLinkBackup.ini is used:
        self.assertIn(self.ini_path, result.output)

        # check the defaults:
        self.assertIn("'database_name': ':memory:',", result.output)
        self.assertIn("'default_new_path_mode': 448,", result.output)
        self.assertIn("'hash_name': 'sha512',", result.output)
        self.assertEqual(result.exit_code,0)

        # go into a new temp dir, without a .ini:
        runner = CliRunner()
        with runner.isolated_filesystem():
            phlb_config._load(force=True)
            result = self.invoke_cli("config", "--debug")
            self.assertIn(USER_INI_PATH, result.output)
            self.assertIn("PyHardLinkBackups.sqlite3", result.output)

    def test_default(self):
        os.remove(self.ini_path) # remove unittests .ini
        phlb_config._config=None

        result = self.invoke_cli("config", "--debug")
        print(result.output)

        # check if created
        self.assertIn(USER_INI_PATH, result.output)
        self.assertTrue(os.path.isfile(USER_INI_PATH))

        # check the defaults:
        self.assertIn("PyHardLinkBackups.sqlite3", result.output)

    def test_overwrite(self):
        """
        test if a .ini in current work dir will overwrite settings
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("PyHardLinkBackup.ini", 'w') as ini:
                ini.write("[foo]\n")
                ini.write("hash_name=md5\n")

            phlb_config._load(force=True)

            result = self.invoke_cli("config", "--debug")
            self.assertIn("PyHardLinkBackup", result.output)

            ini_path=os.path.join(os.getcwd(), "PyHardLinkBackup.ini")
            self.assertIn(ini_path, result.output)

            self.assertIn("'hash_name': 'md5',", result.output)
            self.assertEqual(result.exit_code,0)
