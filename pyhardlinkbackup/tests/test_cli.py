import unittest

from click.testing import CliRunner
from django_tools.unittest_utils.assertments import assert_pformat_equal

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.phlb_cli import cli


class TestCli(unittest.TestCase):
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        # print(result.output)
        self.assertIn("pyhardlinkbackup", result.output)
        self.assertIn("backup", result.output)
        self.assertIn("config", result.output)
        self.assertIn("helper", result.output)
        self.assertIn("verify", result.output)
        assert_pformat_equal(result.exit_code, 0)

    def test_backup_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["backup", "--help"])
        # print(result.output)
        self.assertIn("backup [OPTIONS] PATH", result.output)
        assert_pformat_equal(result.exit_code, 0)

    def test_config_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "--help"])
        # print(result.output)
        self.assertIn("config [OPTIONS]", result.output)
        assert_pformat_equal(result.exit_code, 0)

    def test_helper_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["helper", "--help"])
        # print(result.output)
        self.assertIn("helper [OPTIONS]", result.output)
        assert_pformat_equal(result.exit_code, 0)
        assert_pformat_equal(result.exit_code, 0)

    def test_verify_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["verify", "--help"])
        # print(result.output)
        self.assertIn("verify [OPTIONS]", result.output)
        assert_pformat_equal(result.exit_code, 0)
