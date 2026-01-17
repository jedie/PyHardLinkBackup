import shutil
import tempfile
from pathlib import Path
from unittest import TestCase

from bx_py_utils.test_utils.redirect import RedirectOut
from cli_base.cli_tools.test_utils.assertion import assert_in

from PyHardLinkBackup.compare_backup import CompareResult, LoggingManager, compare_tree
from PyHardLinkBackup.logging_setup import DEFAULT_LOG_FILE_LEVEL
from PyHardLinkBackup.utilities.file_hash_database import FileHashDatabase
from PyHardLinkBackup.utilities.file_size_database import FileSizeDatabase
from PyHardLinkBackup.utilities.filesystem import hash_file


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
    with RedirectOut() as redirected_out:
        result = compare_tree(
            src_root=src_root,
            backup_root=backup_root,
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


class CompareBackupTestCase(TestCase):
    def test_happy_path(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as backup_dir:
            src_root = Path(src_dir).resolve()
            backup_root = Path(backup_dir).resolve()

            # Setup backup structure
            phlb_conf_dir = backup_root / '.phlb'
            phlb_conf_dir.mkdir()

            compare_main_dir = backup_root / src_root.name
            compare_main_dir.mkdir()

            # Create some "older" compare dirs
            (compare_main_dir / '2025-12-31-235959').mkdir()
            (compare_main_dir / '2026-01-10-235959').mkdir()

            # Create "last" backup dir:
            timestamp = '2026-01-17-120000'
            last_backup_dir = compare_main_dir / timestamp
            last_backup_dir.mkdir()

            # Create source files
            (src_root / 'small_file.txt').write_text('hello world')
            (src_root / 'large_file_missing.txt').write_bytes(b'X' * FileSizeDatabase.MIN_SIZE)
            large_file_in_dbs = src_root / 'large_file_in_dbs.txt'
            large_file_in_dbs.write_bytes(b'Y' * (FileSizeDatabase.MIN_SIZE + 1))

            # Copy files to backup
            total_size = 0
            total_file_count = 0
            for file_path in src_root.iterdir():
                shutil.copy2(file_path, last_backup_dir / file_path.name)
                total_size += file_path.stat().st_size
                total_file_count += 1
            self.assertEqual(total_file_count, 3)
            self.assertEqual(total_size, 2012)

            # Create databases and add values from 'large_file_in_dbs.txt'
            size_db = FileSizeDatabase(phlb_conf_dir)
            size_db.add(FileSizeDatabase.MIN_SIZE + 1)
            hash_db = FileHashDatabase(backup_root, phlb_conf_dir)
            src_hash = hash_file(large_file_in_dbs)
            hash_db[src_hash] = last_backup_dir / 'large_file_in_dbs.txt'

            #######################################################################################
            # Run compare_tree

            with RedirectOut() as redirected_out:
                result = compare_tree(
                    src_root=src_root,
                    backup_root=backup_root,
                    excludes=(),
                    log_manager=LoggingManager(
                        console_level='info',
                        file_level=DEFAULT_LOG_FILE_LEVEL,
                    ),
                )
            self.assertEqual(redirected_out.stderr, '')
            self.assertIn('Compare completed.', redirected_out.stdout)
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
                src_root=src_root,
                backup_root=backup_root,
                excpected_last_timestamp='2026-01-17-120000',
                excpected_total_file_count=total_file_count,
                excpected_successful_file_count=total_file_count,
                excpected_error_count=0,
            )
