import unittest

import click
from click.testing import CliRunner

from PyHardLinkBackup.phlb_cli import cli

class TestConfig(unittest.TestCase):
    def test_default(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "--debug"])
        # print(result.output)
        self.assertIn("PyHardLinkBackup", result.output)
        self.assertIn("/PyHardLinkBackup.ini", result.output)
        self.assertIn("PyHardLinkBackups.sqlite3", result.output)
        self.assertIn("'default_new_path_mode': 448,", result.output)
        self.assertIn("'hash_name': 'sha512',", result.output)
        self.assertEqual(result.exit_code,0)
