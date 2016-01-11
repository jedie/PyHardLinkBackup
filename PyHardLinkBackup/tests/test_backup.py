import os
import sys
import unittest

from click.testing import CliRunner

from PyHardLinkBackup.phlb.config import phlb_config

from PyHardLinkBackup.phlb_cli import cli


THIS_FILEPATH = os.path.dirname(__file__)


class TestBackup(unittest.TestCase):
    def setUp(self):
        phlb_config._load(force=True)

    def test_backup(self):
        phlb_config.sub_dir_formatter="A%Y-%m-%d-%H%M%S"

        runner = CliRunner()
        result = runner.invoke(cli, ["backup", THIS_FILEPATH])
        print(result.output, file=sys.stderr)
        self.assertIn("PyHardLinkBackup", result.output)

        # change if more test files are created!
        self.assertIn("scanned 4 files", result.output)

        self.assertIn(os.path.join("PyHardLinkBackups", "tests", "A"), result.output)

        self.assertIn("Backup done", result.output)



