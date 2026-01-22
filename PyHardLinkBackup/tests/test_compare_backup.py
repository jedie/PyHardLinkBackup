import shutil
from pathlib import Path
from unittest import TestCase

from bx_py_utils.test_utils.redirect import RedirectOut
from cli_base.cli_tools.test_utils.assertion import assert_in
from cli_base.cli_tools.test_utils.rich_test_utils import NoColorEnvRich
from freezegun import freeze_time

from PyHardLinkBackup.compare_backup import CompareResult, LoggingManager, compare_tree
from PyHardLinkBackup.logging_setup import DEFAULT_LOG_FILE_LEVEL
from PyHardLinkBackup.utilities.file_hash_database import FileHashDatabase
from PyHardLinkBackup.utilities.file_size_database import FileSizeDatabase
from PyHardLinkBackup.utilities.filesystem import hash_file
from PyHardLinkBackup.utilities.rich_utils import NoopProgress
from PyHardLinkBackup.utilities.tests.unittest_utilities import (
    CollectOpenFiles,
    PyHardLinkBackupTestCaseMixin,
)


def assert_compare_backup(
    test_case: TestCase,
    src_root: Path,
    backup_root: Path,
    excpected_last_timestamp: str,
    excpected_total_file_count: int,
    excpected_successful_file_count: int,
    std_out_parts: tuple[str, ...] = ('Compare completed.',),
    excludes: tuple[str, ...] = (),
    excpected_error_count: int = 0,
) -> None:
    with (
        NoColorEnvRich(
            width=200,  # Wide width to avoid line breaks in test output that failed assert_in()
        ),
        RedirectOut() as redirected_out,
    ):
        result = compare_tree(
            src_root=src_root,
            backup_root=backup_root,
            one_file_system=True,
            excludes=excludes,
            log_manager=LoggingManager(
                console_level='info',
                file_level=DEFAULT_LOG_FILE_LEVEL,
            ),
        )
    stdout = redirected_out.stdout
    test_case.assertEqual(redirected_out.stderr, '', stdout)

    assert_in(content=stdout, parts=std_out_parts)

    test_case.assertEqual(result.last_timestamp, excpected_last_timestamp, stdout)
    test_case.assertEqual(result.total_file_count, excpected_total_file_count, stdout)
    test_case.assertEqual(result.successful_file_count, excpected_successful_file_count, stdout)
    test_case.assertEqual(result.error_count, excpected_error_count, stdout)


class CompareBackupTestCase(PyHardLinkBackupTestCaseMixin, TestCase):
    def test_happy_path(self):
        # Setup backup structure
        phlb_conf_dir = self.backup_root / '.phlb'
        phlb_conf_dir.mkdir()

        # Create some "older" compare dirs
        (self.backup_root / '2025-12-31-235959').mkdir()
        (self.backup_root / '2026-01-10-235959').mkdir()

        # Create "last" backup dir:
        timestamp = '2026-01-17-120000'
        last_backup_dir = self.backup_root / self.src_root.name / timestamp
        last_backup_dir.mkdir(parents=True)

        # Create source files
        (self.src_root / 'small_file.txt').write_text('hello world')
        (self.src_root / 'large_file_missing.txt').write_bytes(b'X' * FileSizeDatabase.MIN_SIZE)
        large_file_in_dbs = self.src_root / 'large_file_in_dbs.txt'
        large_file_in_dbs.write_bytes(b'Y' * (FileSizeDatabase.MIN_SIZE + 1))

        # Copy files to backup
        total_size = 0
        total_file_count = 0
        for file_path in self.src_root.iterdir():
            shutil.copy2(file_path, last_backup_dir / file_path.name)
            total_size += file_path.stat().st_size
            total_file_count += 1
        self.assertEqual(total_file_count, 3)
        self.assertEqual(total_size, 2012)

        # Create databases and add values from 'large_file_in_dbs.txt'
        size_db = FileSizeDatabase(phlb_conf_dir)
        size_db.add(FileSizeDatabase.MIN_SIZE + 1)
        hash_db = FileHashDatabase(self.backup_root, phlb_conf_dir)
        src_hash = hash_file(large_file_in_dbs, progress=NoopProgress(), total_size=1234)
        hash_db[src_hash] = last_backup_dir / 'large_file_in_dbs.txt'

        #######################################################################################
        # Run compare_tree

        with (
            CollectOpenFiles(self.temp_path) as collector,
            freeze_time('2026-01-18T22:12:34+0000', auto_tick_seconds=0),
            RedirectOut() as redirected_out,
        ):
            result = compare_tree(
                src_root=self.src_root,
                backup_root=self.backup_root,
                one_file_system=True,
                excludes=(),
                log_manager=LoggingManager(
                    console_level='info',
                    file_level=DEFAULT_LOG_FILE_LEVEL,
                ),
            )
        self.assertEqual(redirected_out.stderr, '')
        self.assertIn('Compare completed.', redirected_out.stdout)
        self.assertEqual(
            sorted(collector.opened_for_read),
            [
                'rb backups/source/2026-01-17-120000/large_file_in_dbs.txt',
                'rb backups/source/2026-01-17-120000/large_file_missing.txt',
                'rb backups/source/2026-01-17-120000/small_file.txt',
                'rb source/large_file_in_dbs.txt',
                'rb source/large_file_missing.txt',
                'rb source/small_file.txt',
            ],
        )
        self.assertEqual(
            collector.opened_for_write,
            [
                'a backups/source/2026-01-18-221234-compare.log',
                'w backups/source/2026-01-18-221234-summary.txt',
            ],
        )
        self.assertEqual(
            result,
            CompareResult(
                last_timestamp='2026-01-17-120000',
                compare_dir=last_backup_dir,
                log_file=result.log_file,
                total_file_count=total_file_count,
                total_size=total_size,
                src_file_new_count=0,
                file_size_missmatch=0,
                file_hash_missmatch=0,
                small_file_count=1,
                size_db_missing_count=1,
                hash_db_missing_count=1,
                successful_file_count=total_file_count,
                error_count=0,
            ),
            redirected_out.stdout,
        )

        #######################################################################################
        # Check again with our test helper:

        assert_compare_backup(
            test_case=self,
            src_root=self.src_root,
            backup_root=self.backup_root,
            excpected_last_timestamp='2026-01-17-120000',
            excpected_total_file_count=total_file_count,
            excpected_successful_file_count=total_file_count,
            excpected_error_count=0,
        )
