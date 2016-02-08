import os
import pathlib
import pprint
import sys
import tempfile
import unittest
from unittest import mock

import io

from PyHardLinkBackup.backup_app.models import BackupRun, BackupEntry
from click.testing import CliRunner

from PyHardLinkBackup.phlb.config import phlb_config
from PyHardLinkBackup.phlb_cli import cli
from PyHardLinkBackup.tests.base import BaseCreatedTwoBackupsTestCase, BaseCreatedOneBackupsTestCase, \
    BaseSourceDirTestCase, BaseWithSourceFilesTestCase
from PyHardLinkBackup.tests.utils import UnittestFileSystemHelper, PatchOpen
from PyHardLinkBackup.phlb.pathlib2 import Path2


class TestBackup(BaseSourceDirTestCase):
    """
    Tests with empty "source unittests files" directory under /temp/
    """
    def test_no_files(self):
        result = self.invoke_cli("backup", self.source_path)
        print(result.output)
        self.assertIn("0 Bytes in 0 files to backup.", result.output)
        self.assertIn("Files to backup: 0 files", result.output)
        self.assertNotIn("omitted files", result.output)
        self.assertIn("fast backup: 0 files", result.output)

    def test_same_size_different_content(self):
        test_file1=pathlib.Path(self.source_path, "dirA", "file.txt")
        os.mkdir(str(test_file1.parent))
        with test_file1.open("w") as f:
            f.write("content1")

        test_file2=pathlib.Path(self.source_path, "dirB", "file.txt")
        os.mkdir(str(test_file2.parent))
        with test_file2.open("w") as f:
            f.write("content2")

        self.assertEqual(os.stat(str(test_file1)).st_size, 8)
        self.assertEqual(os.stat(str(test_file2)).st_size, 8)

        result = self.invoke_cli("backup", self.source_path)
        print(result.output)

        self.assertIn("16 Bytes in 2 files to backup.", result.output)
        self.assertNotIn("omitted files", result.output)
        self.assertIn("fast backup: 0 files", result.output)
        self.assertIn("new content saved: 2 files (16 Bytes 100.0%)", result.output)
        self.assertIn("stint space via hardlinks: 0 files (0 Bytes 0.0%)", result.output)

        self.assert_backup_fs_count(1) # there are tree backups in filesystem

    def test_mtime(self):
        test_file=pathlib.Path(self.source_path, "file.txt")
        test_file.touch()
        atime_ns = 123456789012345678
        mtime_ns = 123456789012345678
        os.utime(str(test_file), ns=(atime_ns, mtime_ns))
        self.assert_file_mtime_ns(test_file, mtime_ns)

        result = self.invoke_cli("backup", self.source_path)
        print(result.output)

        # check mtime
        backup_path1 = self.get_newest_backup_path()
        backup_file1=pathlib.Path(backup_path1, "file.txt")
        self.assertTrue(backup_file1.is_file())
        self.assert_file_mtime_ns(backup_file1, mtime_ns)

        # source file not changed?
        self.assert_file_mtime_ns(test_file, mtime_ns)

        # check mtime in database
        backup_entries = BackupEntry.objects.all()
        self.assertEqual(backup_entries.count(), 1)
        backup_entry = backup_entries[0]
        self.assert_mtime_ns(backup_entry.file_mtime_ns, mtime_ns)

        # check normal output
        self.assertIn("0 Bytes in 1 files to backup.", result.output)
        self.assertIn("fast backup: 0 files", result.output)
        self.assertIn("new content saved: 1 files (0 Bytes 0.0%)", result.output)
        self.assertIn("stint space via hardlinks: 0 files (0 Bytes 0.0%)", result.output)

        # Test second run:
        result = self.invoke_cli("backup", self.source_path)
        print(result.output)

        # check mtime
        backup_path2 = self.get_newest_backup_path()
        backup_file2=pathlib.Path(backup_path2, "file.txt")
        self.assertTrue(backup_file2.is_file())
        self.assert_file_mtime_ns(backup_file2, mtime_ns)

        # first file not changed?!?
        self.assert_file_mtime_ns(backup_file1, mtime_ns)

        # check normal output
        self.assertIn("0 Bytes in 1 files to backup.", result.output)
        self.assertIn("fast backup: 1 files", result.output)
        self.assertIn("new content saved: 0 files (0 Bytes 0.0%)", result.output)
        self.assertIn("stint space via hardlinks: 1 files (0 Bytes 0.0%)", result.output)

    def test_extended_path(self):
        """
        Backup a very long path
        Test the \\?\ notation under Windows as a work-a-round for MAX_PATH.
        see:
        https://github.com/jedie/PyHardLinkBackup/issues/18
        https://bugs.python.org/issue18199
        https://www.python-forum.de/viewtopic.php?f=1&t=37931#p290999
        """
        new_path = Path2(self.source_path, "A"*255, "B"*255)
        new_path.makedirs()
        test_filepath = Path2(new_path, "X")
        with test_filepath.open("w") as f:
            f.write("File content under a very long path.")

        result = self.invoke_cli("backup", self.source_path)
        print(result.output)
        self.assertIn("36 Bytes in 1 files to backup.", result.output)
        self.assertIn("new content saved: 1 files (36 Bytes 100.0%)", result.output)
        self.assertNotIn("omitted files", result.output)
        self.assertIn("stint space via hardlinks: 0 files (0 Bytes 0.0%)", result.output)


class WithSourceFilesTestCase(BaseWithSourceFilesTestCase):
    def test_print_update(self):
        first_run_result = self.invoke_cli("backup", self.source_path)
        print("FIRST RUN OUTPUT:\n", first_run_result.output)

        # We should not have in between update info with default settings and duration
        self.assertNotIn("Update info:", first_run_result.output)

        self.assertIn("new content saved: 5 files (106 Bytes 100.0%)", first_run_result.output)
        self.assertIn("stint space via hardlinks: 0 files (0 Bytes 0.0%)", first_run_result.output)

        self.simulate_slow_speed(0.1) # slow down backup
        phlb_config.print_update_interval=0.1 # Very often status infos

        second_run_result = self.invoke_cli("backup", self.source_path)
        print("SECOND RUN OUTPUT:\n", second_run_result.output)

        # Now we should have in between update info
        self.assertIn("Slow down speed for tests activated!", second_run_result.output)
        self.assertIn("Slow down speed for tests!", second_run_result.output)
        self.assertIn("Update info:", second_run_result.output)

        self.assertIn("new content saved: 0 files (0 Bytes 0.0%)", second_run_result.output)
        self.assertIn("stint space via hardlinks: 5 files (106 Bytes 100.0%)", second_run_result.output)

        # run_log = self.get_last_log_content()
        # print("+++ LAST LOGGING OUTPUT: +++\n", run_log)
        # self.assertIn("was renamed to", run_log)

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

        fs_items=os.listdir(self.backup_path)
        self.assertEqual(fs_items, ['ForcedName'])

        self.assertIn("/PyHardLinkBackups/ForcedName/".replace("/", os.sep), result.output)

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
        with mock.patch('io.open', PatchOpen(open, deny_paths)) as p:
            # Work PatchOpen() ?
            content = io.open(os.path.join(self.source_path, "root_file_A.txt"), "r").read()
            self.assertEqual(content, "The root file A content.")
            self.assertEqual(p.call_count, 1)
            self.assertEqual(p.raise_count, 0)
            try:
                io.open(deny_paths[0], "r").read()
            except OSError as err:
                self.assertEqual("%s" % err, "unittests raise")
            self.assertEqual(p.call_count, 2)
            self.assertEqual(p.raise_count, 1)

            result = self.invoke_cli("backup", self.source_path)
            print(result.output)
            self.assertEqual(p.raise_count, 3)

        self.assertIn("unittests raise", result.output) # Does the test patch worked?

        self.assertIn("106 Bytes in 5 files to backup.", result.output)
        self.assertIn("WARNING: 2 omitted files", result.output)
        self.assertIn("new content saved: 3 files (64 Bytes 60.4%)", result.output)
        self.assertIn("stint space via hardlinks: 0 files (0 Bytes 0.0%)", result.output)

        self.assertEqual(os.listdir(self.backup_path), ["source unittests files"])
        self.assert_backup_fs_count(1)

        log_content = self.get_last_log_content()
        print(log_content)
        self.assertIn("Skip file", log_content)
        self.assertIn(
            "/source unittests files/root_file_B.txt error: unittests raise".replace("/", os.sep),
            log_content
        )
        self.assertIn(
            "/source unittests files/sub dir B/sub_file.txt error: unittests raise".replace("/", os.sep),
            log_content
        )
        self.assertIn("unittests raise", log_content)

    def test_unexpected_error(self):
        origin_open = os.utime
        def patched_open(filename, *args, **kwargs):
            if "dir_A_file" in filename: # will match on two files!
                # raise a extraordinary error that will normally not catch ;)
                raise TabError("test raise")
            return origin_open(filename, *args, **kwargs)

        with mock.patch("os.utime", patched_open):
            result = self.invoke_cli("backup", self.source_path)
            print(result.output)

        summary = self.get_last_summary_content()

        self.assertIn("Backup aborted with a unexpected error", result.output)
        self.assertIn("Backup aborted with a unexpected error", summary)

        self.assertIn("Traceback (most recent call last):", result.output)
        self.assertIn("Traceback (most recent call last):", summary)

        self.assertIn("TabError: test raise", result.output)
        self.assertIn("TabError: test raise", summary)

        self.assertIn("Files to backup: 5 files", result.output)
        self.assertIn("Files to backup: 5 files", summary)

        self.assertIn("WARNING: 2 omitted files!", result.output)
        self.assertIn("WARNING: 2 omitted files!", summary)

        self.assertIn("---END---", result.output)
        self.assertIn("---END---", summary)

    def test_keyboard_interrupt(self):
        origin_open = os.utime
        def patched_open(filename, *args, **kwargs):
            if filename.endswith("dir_A_file_A.txt"):
                raise KeyboardInterrupt
            return origin_open(filename, *args, **kwargs)

        with mock.patch("os.utime", patched_open):
            result = self.invoke_cli("backup", self.source_path)
            print(result.output)

        summary = self.get_last_summary_content()

        self.assertIn("Abort backup, because user hits the interrupt key during execution!", result.output)
        self.assertIn("Abort backup, because user hits the interrupt key during execution!", summary)

        self.assertNotIn("Traceback", result.output)
        self.assertNotIn("Traceback", summary)

        # Is the summary with right calculate file count?
        self.assertIn("Files to backup: 5 files", result.output)
        self.assertIn("Files to backup: 5 files", summary)
        self.assertIn("WARNING: 3 omitted files!", result.output)
        self.assertIn("WARNING: 3 omitted files!", summary)
        self.assertIn("new content saved: 2 files (38 Bytes 35.8%)", result.output)
        self.assertIn("new content saved: 2 files (38 Bytes 35.8%)", summary)
        self.assertIn("stint space via hardlinks: 0 files (0 Bytes 0.0%)", result.output)
        self.assertIn("stint space via hardlinks: 0 files (0 Bytes 0.0%)", summary)

        self.assertIn("---END---", result.output)
        self.assertIn("---END---", summary)

    @unittest.skipIf(True, "TODO!")
    def test_skip_dirs(self):
        # TODO: test phlb_config.SKIP_DIRS
        pass

    @unittest.skipIf(True, "TODO!")
    def test_skip_patterns(self):
        # TODO: test phlb_config SKIP_PATTERNS
        pass



class TestOneBackups(BaseCreatedOneBackupsTestCase):
    def test_summary(self):
        summary_filepath = pathlib.Path(self.first_run_path + " summary.txt")
        self.assertTrue(summary_filepath.is_file(), "%s doesn't exist" % summary_filepath)

        with summary_filepath.open("r") as f: # Path().read_text() is new in Py 2.5
            summary_content = f.read()
        print(summary_content)

        self.assertIn("Backup done:", summary_content)
        self.assertIn("Source file sizes: 106 Bytes", summary_content)
        self.assertIn("new content saved: 5 files (106 Bytes 100.0%)", summary_content)
        self.assertIn("stint space via hardlinks: 0 files (0 Bytes 0.0%)", summary_content)

    def test_log_file(self):
        log_content = self.get_log_content(self.first_run_log)

        print(log_content)
        self.assertIn("Backup", log_content)
        self.assertIn("Start low level logging", log_content)

    def test_not_existing_old_backup_files(self):
        paths = (
            os.path.join(self.first_run_path, "root_file_B.txt"),
            os.path.join(self.first_run_path, "sub dir B", "sub_file.txt"),
        )
        for path in paths:
            print("Delete: %r" % path)
            os.remove(path)

        result = self.invoke_cli("backup", self.source_path)
        print(result.output)

        log_content = self.get_log_content(self.first_run_log)
        parts = (
            "Can't link", # error message about removed source file
            "Mark", "with 'no link source'", # Mark BackupEntry
        )
        for part in parts:
            self.assertIn(part, log_content)

        self.assertIn("106 Bytes in 5 files to backup.", result.output)

        # No skipped files, because they are used from source
        self.assertNotIn("omitted files", result.output)

        # 5 source files - 2 removed files:
        self.assertIn("fast backup: 3 files", result.output)

        # The two removed files:
        self.assertIn("new content saved: 2 files (42 Bytes 39.6%)", result.output)

        # 5-2 files from old backup
        self.assertIn("stint space via hardlinks: 3 files (64 Bytes 60.4%)", result.output)

        self.assertEqual(os.listdir(self.backup_path), ["source unittests files"])
        self.assert_backup_fs_count(2)

    def test_if_os_link_failed(self):

        origin_os_link = os.link
        def patched_open(source, link_name):
            if source.endswith("root_file_B.txt"):
                raise IOError("unittests raise")
            return origin_os_link(source, link_name)

        with mock.patch('os.link', patched_open):
            result = self.invoke_cli("backup", self.source_path)
            print(result.output)

        self.assertIn("Can't link", result.output)
        self.assertIn("root_file_B.txt': unittests raise", result.output)

        self.assertIn("106 Bytes in 5 files to backup.", result.output)
        self.assertNotIn("omitted files", result.output)
        self.assertIn("fast backup: 4 files", result.output)
        self.assertIn("new content saved: 1 files (24 Bytes 22.6%)", result.output)
        self.assertIn("stint space via hardlinks: 4 files (82 Bytes 77.4%)", result.output)

        self.assertEqual(os.listdir(self.backup_path), ["source unittests files"])
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
        self.assertEqual(backup_runs.count(), 1)
        backup_run = backup_runs[0]
        backup_run.completed = False
        backup_run.save()

        result = self.invoke_cli("backup", self.source_path)
        print(result.output)
        backup_path = self.get_newest_backup_path()
        self.assert_backuped_files(backup_path, backup_run_pk=2)

        self.assertIn("106 Bytes in 5 files to backup.", result.output)
        self.assertNotIn("omitted files", result.output)

        # Can't use the fast backup, because all previous backups are not complete
        self.assertIn("fast backup: 0 files", result.output)

        self.assertIn("new content saved: 0 files (0 Bytes 0.0%)", result.output)
        self.assertIn("stint space via hardlinks: 5 files (106 Bytes 100.0%)", result.output)


class TestTwoBackups(BaseCreatedTwoBackupsTestCase):
    def test_changed_file(self):
        filepath = os.path.join(self.source_path, "sub dir A", "dir_A_file_B.txt")
        with open(filepath, "w") as f:
            f.write(">>> The new content! <<<")

        # run backup
        result = self.invoke_cli("backup", self.source_path)

        print(result.output)

        self.assertIn("110 Bytes in 5 files to backup.", result.output)
        self.assertNotIn("omitted files", result.output)
        self.assertIn("fast backup: 4 files", result.output)
        self.assertIn("new content saved: 1 files (24 Bytes 21.8%)", result.output)
        self.assertIn("stint space via hardlinks: 4 files (86 Bytes 78.2%)", result.output)

        self.assert_backup_fs_count(3) # there are tree backups in filesystem
        backup_path = self.get_newest_backup_path()

        fs_helper = UnittestFileSystemHelper()
        #fs_helper.print_tree(self.backup_path)
        tree_list = fs_helper.pformat_tree(backup_path, with_timestamps=False)
        pprint.pprint(tree_list,indent=0, width=200)
        self.assertListEqual(tree_list, [
            backup_path,
            'phlb_config.ini                F - [BACKUP_RUN]\nprimary_key = 3\n\n',
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
