import shutil
import tempfile
from pathlib import Path
from unittest import TestCase

from bx_py_utils.test_utils.redirect import RedirectOut
from cli_base.cli_tools.test_utils.base_testcases import OutputMustCapturedTestCaseMixin

from PyHardLinkBackup.compare_backup import CompareResult, LoggingManager, compare_tree
from PyHardLinkBackup.logging_setup import DEFAULT_LOG_FILE_LEVEL
from PyHardLinkBackup.utilities.file_hash_database import FileHashDatabase
from PyHardLinkBackup.utilities.file_size_database import FileSizeDatabase
from PyHardLinkBackup.utilities.filesystem import hash_file


class CompareBackupTestCase(OutputMustCapturedTestCaseMixin, TestCase):
    def test_happy_path(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as backup_dir:
            src_root = Path(src_dir).resolve()
            backup_root = Path(backup_dir).resolve()

            # Setup backup structure
            phlb_conf_dir = backup_root / '.phlb'
            phlb_conf_dir.mkdir()

            compare_main_dir = backup_root / src_root.name
            compare_main_dir.mkdir()

            timestamp = '2026-01-17-120000'
            compare_dir = compare_main_dir / timestamp
            compare_dir.mkdir()

            # Create source files
            (src_root / 'small_file.txt').write_text('hello world')
            (src_root / 'large_file_missing.txt').write_bytes(b'X' * FileSizeDatabase.MIN_SIZE)
            large_file_in_dbs = src_root / 'large_file_in_dbs.txt'
            large_file_in_dbs.write_bytes(b'Y' * (FileSizeDatabase.MIN_SIZE + 1))

            # Copy files to backup
            total_size = 0
            total_file_count = 0
            for file_path in src_root.iterdir():
                shutil.copy2(file_path, compare_dir / file_path.name)
                total_size += file_path.stat().st_size
                total_file_count += 1
            self.assertEqual(total_file_count, 3)
            self.assertEqual(total_size, 2012)

            # Create databases and add values from 'large_file_in_dbs.txt'
            size_db = FileSizeDatabase(phlb_conf_dir)
            size_db.add(FileSizeDatabase.MIN_SIZE + 1)
            hash_db = FileHashDatabase(backup_root, phlb_conf_dir)
            src_hash = hash_file(large_file_in_dbs)
            hash_db[src_hash] = compare_dir / 'large_file_in_dbs.txt'

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
                    compare_dir=compare_dir,
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
