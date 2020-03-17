import datetime
import os
import pathlib
import pprint
import sys
from unittest import mock

from click.testing import CliRunner
from django_tools.unittest_utils.assertments import (
    assert_is_dir,
    assert_is_file,
    assert_pformat_equal,
    assert_startswith
)

# https://github.com/jedie/pathlib_revised/
from pathlib_revised import Path2

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.backup_app.models import BackupEntry, BackupRun
from pyhardlinkbackup.phlb.cli import cli
from pyhardlinkbackup.phlb.config import phlb_config
from pyhardlinkbackup.tests.base import (
    BaseCreatedOneBackupsTestCase,
    BaseCreatedTwoBackupsTestCase,
    BaseSourceDirTestCase,
    BaseWithSourceFilesTestCase
)
from pyhardlinkbackup.tests.mock_datetime import mock_datetime_now
from pyhardlinkbackup.tests.utils import PatchOpen, UnittestFileSystemHelper


class TestBackup(BaseSourceDirTestCase):
    """
    Tests with empty "source unittests files" directory under /temp/
    """

    def test_no_files(self):
        dt = datetime.datetime(
            year=2020, month=1, day=2, hour=3, minute=4, second=5, microsecond=6
        )
        with mock_datetime_now(dt):
            result = self.invoke_cli("backup", self.source_path)

        print(result.output)
        self.assertIn("Start backup: 2020-01-02-030405-000006", result.output)

        self.assertIn(" * Files to backup: 0 files", result.output)
        self.assertIn(" * Source file sizes: 0 Byte", result.output)
        self.assertNotIn("omitted files", result.output)
        self.assertIn(" * fast backup: 0 files", result.output)

        self.assertIn("source unittests files/2020-01-02-030405-000006.log", result.output)

        fs_helper = UnittestFileSystemHelper()
        tree_list = fs_helper.pformat_tree(self.backup_sub_path, with_timestamps=True)
        pprint.pprint(tree_list, indent=0, width=200)

        # The new backup directory:
        assert_is_dir(pathlib.Path(self.backup_sub_path, '2020-01-02-030405-000006'))

        assert_is_file(pathlib.Path(
            self.backup_sub_path, '2020-01-02-030405-000006', 'phlb_config.ini')
        )

        log_file_path = pathlib.Path(self.backup_sub_path, '2020-01-02-030405-000006.log')
        assert_is_file(log_file_path)
        logs = log_file_path.read_text()
        print('*' * 100)
        print(logs)
        print('*' * 100)
        assert_startswith(logs, 'Truncate log file in setUp()')

        self.assert_backup_fs_count(1)

    def test_same_size_different_content(self):
        test_file1 = pathlib.Path(self.source_path, "dirA", "file.txt")
        os.mkdir(str(test_file1.parent))
        with test_file1.open("w") as f:
            f.write("content1")

        test_file2 = pathlib.Path(self.source_path, "dirB", "file.txt")
        os.mkdir(str(test_file2.parent))
        with test_file2.open("w") as f:
            f.write("content2")

        assert_pformat_equal(os.stat(str(test_file1)).st_size, 8)
        assert_pformat_equal(os.stat(str(test_file2)).st_size, 8)

        result = self.invoke_cli("backup", self.source_path)
        print(result.output)

        self.assertIn(" * Files to backup: 2 files", result.output)
        self.assertIn(" * Source file sizes: 16 Bytes", result.output)
        self.assertNotIn("omitted files", result.output)
        self.assertIn(" * fast backup: 0 files", result.output)
        self.assertIn(" * new content saved: 2 files (16 Bytes 100.0%)", result.output)
        self.assertIn(" * stint space via hardlinks: 0 files (0 Byte 0.0%)", result.output)

        self.assert_backup_fs_count(1)  # there are tree backups in filesystem

    def test_mtime(self):
        test_file = pathlib.Path(self.source_path, "file.txt")
        test_file.touch()
        atime_ns = 123456789012345678
        mtime_ns = 123456789012345678
        os.utime(str(test_file), ns=(atime_ns, mtime_ns))
        self.assert_file_mtime_ns(test_file, mtime_ns)

        result = self.invoke_cli("backup", self.source_path)
        print(result.output)

        # check mtime
        backup_path1 = self.get_newest_backup_path()
        backup_file1 = pathlib.Path(backup_path1, "file.txt")
        self.assertTrue(backup_file1.is_file())
        self.assert_file_mtime_ns(backup_file1, mtime_ns)

        # source file not changed?
        self.assert_file_mtime_ns(test_file, mtime_ns)

        # check mtime in database
        backup_entries = BackupEntry.objects.all()
        assert_pformat_equal(backup_entries.count(), 1)
        backup_entry = backup_entries[0]
        self.assert_mtime_ns(backup_entry.file_mtime_ns, mtime_ns)

        # check normal output
        self.assertIn("Backup done", result.output)
        self.assertIn("(1 filesystem items)", result.output)
        self.assertIn("* Files to backup: 1 files", result.output)
        self.assertIn("* Source file sizes: 0 Byte", result.output)
        self.assertIn("* fast backup: 0 files", result.output)
        self.assertIn("* new content saved: 1 files (0 Byte 0.0%)", result.output)
        self.assertIn("* stint space via hardlinks: 0 files (0 Byte 0.0%)", result.output)

        # Test second run:
        result = self.invoke_cli("backup", self.source_path)
        print(result.output)

        # check mtime
        backup_path2 = self.get_newest_backup_path()
        backup_file2 = pathlib.Path(backup_path2, "file.txt")
        self.assertTrue(backup_file2.is_file())
        self.assert_file_mtime_ns(backup_file2, mtime_ns)

        # first file not changed?!?
        self.assert_file_mtime_ns(backup_file1, mtime_ns)

        # check normal output
        self.assertIn("Backup done", result.output)
        self.assertIn("(1 filesystem items)", result.output)
        self.assertIn("* Files to backup: 1 files", result.output)
        self.assertIn("* Source file sizes: 0 Byte", result.output)
        self.assertIn("* fast backup: 1 files", result.output)
        self.assertIn("* new content saved: 0 files (0 Byte 0.0%)", result.output)
        self.assertIn("* stint space via hardlinks: 1 files (0 Byte 0.0%)", result.output)

    def test_extended_path(self):
        """
        Backup a very long path
        Test the \\?\\ notation under Windows as a work-a-round for MAX_PATH.
        see:
        https://github.com/jedie/PyHardLinkBackup/issues/18
        https://bugs.python.org/issue18199
        https://www.python-forum.de/viewtopic.php?f=1&t=37931#p290999
        """
        new_path = Path2(self.source_path, "A" * 255, "B" * 255)
        new_path.makedirs()
        test_filepath = Path2(new_path, "X")
        with test_filepath.open("w") as f:
            f.write("File content under a very long path.")

        result = self.invoke_cli("backup", self.source_path)
        print(result.output)
        self.assertIn("* Files to backup: 1 files", result.output)
        self.assertIn("* Source file sizes: 36 Bytes", result.output)
        self.assertIn("* new content saved: 1 files (36 Bytes 100.0%)", result.output)
        self.assertNotIn("omitted files", result.output)
        self.assertIn("* stint space via hardlinks: 0 files (0 Byte 0.0%)", result.output)


class WithSourceFilesTestCase(BaseWithSourceFilesTestCase):
    def test_print_update(self):
        assert BackupRun.objects.count() == 0

        first_run_result = self.invoke_cli("backup", self.source_path)
        print('_' * 100)
        print("FIRST RUN OUTPUT:\n", first_run_result.output)
        run_log = self.get_last_log_content()
        print("+++ LOGGING OUTPUT: +++\n", run_log)

        assert list(BackupRun.objects.values_list('name', 'completed')) == [('source unittests files', True)]

        self.assertIn("'source unittests files' was backuped 0 time(s)", first_run_result.output)
        self.assertIn("There are 0 backups finished completed.", first_run_result.output)
        self.assertIn(" * new content saved: 5 files (106 Bytes 100.0%)", first_run_result.output)
        self.assertIn(" * stint space via hardlinks: 0 files (0 Byte 0.0%)", first_run_result.output)

        self.simulate_slow_speed(0.1)  # slow down backup
        phlb_config.print_update_interval = 0.1  # Very often status infos

        second_run_result = self.invoke_cli("backup", self.source_path)
        print('_' * 100)
        print("SECOND RUN OUTPUT:\n", second_run_result.output)
        run_log = self.get_last_log_content()
        print("+++ LOGGING OUTPUT: +++\n", run_log)

        assert list(BackupRun.objects.values_list('name', 'completed')) == [
            ('source unittests files', True), ('source unittests files', True)
        ]

        self.assertIn("'source unittests files' was backuped 1 time(s)", second_run_result.output)
        self.assertIn("There are 1 backups finished completed.", second_run_result.output)
        self.assertIn("Slow down speed for tests activated!", second_run_result.output)
        self.assertIn("Slow down speed for tests!", second_run_result.output)

        self.assertIn(" * new content saved: 0 files (0 Byte 0.0%)", second_run_result.output)
        self.assertIn(
            "stint space via hardlinks: 5 files (106 Bytes 100.0%)",
            second_run_result.output)

    def test_no_backupname(self):
        if sys.platform.startswith("win"):
            source_path = "C:\\"
        else:
            source_path = "/"

        runner = CliRunner()
        result = runner.invoke(cli, args=["backup", source_path])

        print(result.output)
        self.assertIn("Error get name for this backup!", result.output)
        self.assertIn("Please use '--name' for force a backup name!", result.output)

        self.assertIsInstance(result.exception, SystemExit)

    def test_force_name(self):
        result = self.invoke_cli("backup", self.source_path, "--name", "ForcedName")
        print(result.output)

        fs_items = os.listdir(self.backup_path)
        assert_pformat_equal(fs_items, ["ForcedName"])

        self.assertIn("/pyhardlinkbackups/ForcedName/".replace("/", os.sep), result.output)

    def test_skip_patterns(self):
        """
        Test if not open able source files, will be skipped
        and the backup will save the other files.
        """
        deny_paths = (
            os.path.join(self.source_path, "root_file_B.txt"),
            os.path.join(self.source_path, "sub dir B", "sub_file.txt"),
        )
        print("Deny path:")
        print("\n".join(deny_paths))

        # pathlib.Path().open() used io.open and not builtins.open !
        with mock.patch("io.open", PatchOpen(open, deny_paths)) as p:
            # Work PatchOpen() ?
            content = pathlib.Path(self.source_path, "root_file_A.txt").read_text()
            assert_pformat_equal(content, "The root file A content.")
            assert p.call_count == 1
            assert p.raise_count == 0
            try:
                pathlib.Path(deny_paths[0]).read_text()
            except OSError as err:
                assert_pformat_equal(f"{err}", "unittests raise")
            assert p.call_count == 2
            assert p.raise_count == 1

            result = self.invoke_cli("backup", self.source_path)
            print(result.output)
            assert p.raise_count == 3

        self.assertIn("unittests raise", result.output)  # Does the test patch worked?

        self.assertIn("Backup done.", result.output)
        self.assertIn("WARNING: 2 omitted files", result.output)
        self.assertIn(" * new content saved: 3 files (64 Bytes 100.0%)", result.output)
        self.assertIn(" * stint space via hardlinks: 0 files (0 Byte 0.0%)", result.output)

        assert_pformat_equal(os.listdir(self.backup_path), ["source unittests files"])
        self.assert_backup_fs_count(1)

        log_content = self.get_last_log_content()
        print('*' * 100)
        print(log_content)
        print('*' * 100)
        self.assertIn("Skip file", log_content)
        self.assertIn("error: unittests raise", log_content)
        self.assertIn(
            "/source unittests files/root_file_B.txt error: unittests raise".replace("/", os.sep), log_content  # noqa
        )
        self.assertIn(
            "/source unittests files/sub dir B/sub_file.txt error: unittests raise".replace("/", os.sep), log_content  # noqa
        )
        self.assertIn("unittests raise", log_content)

    def test_unexpected_error(self):
        origin_open = os.utime

        def patched_open(filename, *args, **kwargs):
            if "dir_A_file" in filename:  # will match on two files!
                # raise a extraordinary error that will normally not catch ;)
                raise TabError("test raise")
            return origin_open(filename, *args, **kwargs)

        with mock.patch("os.utime", patched_open):
            result = self.invoke_cli("backup", self.source_path)
            print(result.output)

        log_content = self.get_last_log_content()

        self.assertIn("Backup aborted with a unexpected error", result.output)
        self.assertIn("Backup aborted with a unexpected error", log_content)

        self.assertIn("Traceback (most recent call last):", result.output)
        self.assertIn("Traceback (most recent call last):", log_content)

        self.assertIn("TabError: test raise", result.output)
        self.assertIn("TabError: test raise", log_content)

        self.assertIn("Please report this Bug here", result.output)
        self.assertIn("Please report this Bug here", log_content)

        self.assertIn("No old backup found with name 'source unittests files'", result.output)
        self.assertIn("No old backup found with name 'source unittests files'", log_content)

    def test_keyboard_interrupt(self):
        origin_open = os.utime

        def patched_open(filename, *args, **kwargs):
            if filename.endswith("dir_A_file_A.txt"):
                # raised in iterfilesystem.main.IterFilesystem.process
                raise KeyboardInterrupt
            return origin_open(filename, *args, **kwargs)

        with mock.patch("os.utime", patched_open):
            result = self.invoke_cli("backup", self.source_path)

        output = result.output
        print("_" * 100)
        print('output:')
        print(output)
        print("=" * 100)
        self.assertIn(
            "*** Abort backup, because user hits the interrupt key during execution! ***",
            output
        )

        log_content = self.get_last_log_content()
        print("_" * 100)
        print('log content:')
        print(log_content)
        print("=" * 100)
        self.assertIn(
            "*** Abort backup, because user hits the interrupt key during execution! ***",
            log_content
        )

        self.assertNotIn("Traceback", output)
        self.assertNotIn("Traceback", log_content)

        # KeyboardInterrupt handled?
        self.assertIn("Backup done in", output)
        self.assertIn("Backup done in", log_content)

        # Correctly finished?
        self.assertIn("---END---", output)
        self.assertIn("---END---", log_content)
        self.assertIn("Backup done.", output)


class TestOneBackups(BaseCreatedOneBackupsTestCase):
    def test_log_file(self):
        log_content = self.get_log_content(self.first_run_log)
        print(log_content)
        self.assertIn("'source unittests files' was backuped 0", log_content)
        self.assertIn(' * Files to backup: 5 files', log_content)
        self.assertIn(' * Source file sizes: 106 Bytes', log_content)
        self.assertIn(' * new content saved: 5 files (106 Bytes 100.0%)', log_content)
        self.assertIn(' * stint space via hardlinks: 0 files (0 Byte 0.0%)', log_content)
        self.assertIn('---END---', log_content)
        self.assertIn('Log file saved here:', log_content)
        self.assertIn('/pyhardlinkbackups/source unittests files/', log_content)

        assert_startswith(log_content, 'Truncate log file in setUp()')
        assert log_content.count('---END---') == 1

    def test_not_existing_old_backup_files(self):
        paths = (
            os.path.join(self.first_run_path, "root_file_B.txt"),
            os.path.join(self.first_run_path, "sub dir B", "sub_file.txt"),
        )
        for path in paths:
            print(f"Delete: {path!r}")
            os.remove(path)

        result = self.invoke_cli("backup", self.source_path)
        print(result.output)

        log_content = self.get_log_content(self.first_run_log)
        print("*" * 100)
        print(log_content)
        print("*" * 100)
        self.assertIn("Old backup file not found", log_content)

        self.assertIn(" * Files to backup: 5 files", result.output)
        self.assertIn(" * Source file sizes: 106 Bytes", result.output)

        # No skipped files, because they are used from source
        self.assertNotIn("omitted files", result.output)

        # 5 source files - 2 removed files:
        self.assertIn(" * fast backup: 3 files", result.output)

        # The two removed files:
        self.assertIn(" * new content saved: 2 files (42 Bytes 39.6%)", result.output)

        # 5-2 files from old backup
        self.assertIn(" * stint space via hardlinks: 3 files (64 Bytes 60.4%)", result.output)

        assert_pformat_equal(os.listdir(self.backup_path), ["source unittests files"])
        self.assert_backup_fs_count(2)

    def test_if_os_link_failed(self):

        origin_os_link = os.link

        def patched_os_link(source, link_name):
            if source.endswith("root_file_B.txt"):
                raise OSError("unittests raise")
            return origin_os_link(source, link_name)

        with mock.patch("os.link", patched_os_link):
            result = self.invoke_cli("backup", self.source_path)
            print(result.output)

        self.assertIn("Can't link", result.output)
        self.assertIn("root_file_B.txt': unittests raise", result.output)

        self.assertNotIn("omitted files", result.output)
        self.assertIn(" * 0 directories skipped", result.output)
        self.assertIn(" * 0 files skipped", result.output)
        self.assertIn(" * Files to backup: 5 files", result.output)
        self.assertIn(" * Source file sizes: 106 Bytes", result.output)
        self.assertIn(" * fast backup: 4 files", result.output)
        self.assertIn(" * new content saved: 1 files (24 Bytes 22.6%)", result.output)
        self.assertIn(" * stint space via hardlinks: 4 files (82 Bytes 77.4%)", result.output)

        assert_pformat_equal(os.listdir(self.backup_path), ["source unittests files"])
        self.assert_backup_fs_count(2)

        log_content = self.get_log_content(self.first_run_log)
        print(log_content)
        self.assertIn("Can't link", log_content)
        self.assertIn("root_file_B.txt': unittests raise", log_content)

        # TODO: Check model no_link_source !

    def test_last_backup_not_complete(self):
        """
        If all previous backups are not complete: All files will be
        compared by content.
        Here we test the code tree that will temporary rename a new
        created backup file and remove it with a hardlink after the
        hash is the same.
        """
        backup_runs = BackupRun.objects.all()
        assert_pformat_equal(backup_runs.count(), 1)
        backup_run = backup_runs[0]
        backup_run.completed = False
        backup_run.save()

        result = self.invoke_cli("backup", self.source_path)
        print(result.output)
        backup_path = self.get_newest_backup_path()
        self.assert_backuped_files(backup_path, backup_run_pk=2)

        self.assertIn(" * Files to backup: 5 files", result.output)
        self.assertIn(" * Source file sizes: 106 Bytes", result.output)
        self.assertNotIn("omitted files", result.output)

        # Can't use the fast backup, because all previous backups are not complete
        self.assertIn(" * fast backup: 0 files", result.output)

        self.assertIn(" * new content saved: 0 files (0 Byte 0.0%)", result.output)
        self.assertIn(" * stint space via hardlinks: 5 files (106 Bytes 100.0%)", result.output)


class TestTwoBackups(BaseCreatedTwoBackupsTestCase):
    def test_changed_file(self):
        filepath = os.path.join(self.source_path, "sub dir A", "dir_A_file_B.txt")
        with open(filepath, "w") as f:
            f.write(">>> The new content! <<<")

        # run backup
        result = self.invoke_cli("backup", self.source_path)

        print(result.output)

        self.assertIn(" * Files to backup: 5 files", result.output)
        self.assertIn(" * Source file sizes: 110 Bytes", result.output)
        self.assertIn(" * fast backup: 4 files", result.output)
        self.assertIn(" * new content saved: 1 files (24 Bytes 21.8%)", result.output)
        self.assertIn(" * stint space via hardlinks: 4 files (86 Bytes 78.2%)", result.output)

        self.assertNotIn("omitted files", result.output)

        self.assert_backup_fs_count(3)  # there are tree backups in filesystem
        backup_path = self.get_newest_backup_path()

        fs_helper = UnittestFileSystemHelper()
        # fs_helper.print_tree(self.backup_path)
        tree_list = fs_helper.pformat_tree(backup_path, with_timestamps=False)
        pprint.pprint(tree_list, indent=0, width=200)
        self.assertListEqual(
            tree_list,
            [
                backup_path,
                "phlb_config.ini                F - [BACKUP_RUN]\nprimary_key = 3\n\n",
                "root_file_A.txt                L - The root file A content.",
                "root_file_A.txt.sha512         F - 13e3e...d7df6",
                "root_file_B.txt                L - The root file B content.",
                "root_file_B.txt.sha512         F - 4bb47...5a181",
                "sub dir A                      D",
                "sub dir A/dir_A_file_A.txt     L - File A in sub dir A.",
                "sub dir A/dir_A_file_A.txt.sha512 F - 89091...f8669",
                "sub dir A/dir_A_file_B.txt     F - >>> The new content! <<<",  # <<-- new file
                "sub dir A/dir_A_file_B.txt.sha512 F - b7203...eb68f",  # <<-- new hash
                "sub dir B                      D",
                "sub dir B/sub_file.txt         L - File in sub dir B.",
                "sub dir B/sub_file.txt.sha512  F - bbe59...dbdbb",
            ],
        )

        # first + second data must be untouched:
        self.assert_first_backup()
        self.assert_second_backup()
