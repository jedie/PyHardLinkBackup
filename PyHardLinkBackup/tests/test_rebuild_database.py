import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

from bx_py_utils.test_utils.redirect import RedirectOut
from cli_base.cli_tools.test_utils.base_testcases import BaseTestCase

from PyHardLinkBackup import rebuild_databases
from PyHardLinkBackup.rebuild_databases import RebuildResult, rebuild, rebuild_one_file
from PyHardLinkBackup.utilities.file_size_database import FileSizeDatabase


def sorted_rglob_paths(path: Path):
    return sorted([str(p.relative_to(path)) for p in path.rglob('*')])


def sorted_rglob_files(path: Path):
    return sorted([str(p.relative_to(path)) for p in path.rglob('*') if p.is_file()])


class RebuildDatabaseTestCase(BaseTestCase):
    def test_happy_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            backup_root = temp_path / 'backup'

            with self.assertRaises(SystemExit), RedirectOut() as redirected_out:
                rebuild(backup_root)

            self.assertEqual(redirected_out.stderr, '')
            self.assertEqual(redirected_out.stdout, f'Error: Backup directory "{backup_root}" does not exist!\n')

            backup_root.mkdir()

            with self.assertRaises(SystemExit), RedirectOut() as redirected_out:
                rebuild(backup_root)

            self.assertEqual(redirected_out.stderr, '')
            self.assertIn('hidden ".phlb" configuration directory is missing', redirected_out.stdout)

            phlb_conf_dir = backup_root / '.phlb'
            phlb_conf_dir.mkdir()

            #######################################################################################
            # Run on empty backup directory:

            self.assertEqual(sorted_rglob_paths(backup_root), ['.phlb'])

            with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG), RedirectOut() as redirected_out:
                rebuild_result = rebuild(backup_root)
            self.assertEqual(
                rebuild_result,
                RebuildResult(
                    process_count=0,
                    process_size=0,
                    added_size_count=0,
                    added_hash_count=0,
                    error_count=0,
                ),
            )
            self.assertEqual(
                sorted_rglob_paths(backup_root),
                [
                    '.phlb',
                    '.phlb/hash-lookup',
                    '.phlb/size-lookup',
                ],
            )
            self.assertEqual(redirected_out.stderr, '')

            #######################################################################################
            # Add one backuped file and run again:

            snapshot_path = backup_root / 'source-name' / '2026-01-15-181709'
            snapshot_path.mkdir(parents=True)

            minimum_file_content = 'X' * FileSizeDatabase.MIN_SIZE
            (snapshot_path / 'file1.txt').write_text(minimum_file_content)

            with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG), RedirectOut() as redirected_out:
                rebuild_result = rebuild(backup_root)
            self.assertEqual(
                rebuild_result,
                RebuildResult(
                    process_count=1,
                    process_size=FileSizeDatabase.MIN_SIZE,
                    added_size_count=1,
                    added_hash_count=1,
                    error_count=0,
                ),
            )

            self.assertEqual(
                sorted_rglob_paths(backup_root),
                [
                    '.phlb',
                    '.phlb/hash-lookup',
                    '.phlb/hash-lookup/bb',
                    '.phlb/hash-lookup/bb/c4',
                    '.phlb/hash-lookup/bb/c4/bbc4de2ca238d1ec41fb622b75b5cf7d31a6d2ac92405043dd8f8220364fefc8',
                    '.phlb/size-lookup',
                    '.phlb/size-lookup/10',
                    '.phlb/size-lookup/10/00',
                    '.phlb/size-lookup/10/00/1000',
                    'source-name',
                    'source-name/2026-01-15-181709',
                    'source-name/2026-01-15-181709/file1.txt',
                ],
            )
            self.assertEqual(
                sorted_rglob_files(backup_root),
                [
                    '.phlb/hash-lookup/bb/c4/bbc4de2ca238d1ec41fb622b75b5cf7d31a6d2ac92405043dd8f8220364fefc8',
                    '.phlb/size-lookup/10/00/1000',
                    'source-name/2026-01-15-181709/file1.txt',
                ],
            )
            self.assertEqual(redirected_out.stderr, '')

            #######################################################################################
            # Add a file with same content and run again:

            minimum_file_content = 'X' * FileSizeDatabase.MIN_SIZE
            (snapshot_path / 'same_content.txt').write_text(minimum_file_content)

            with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG), RedirectOut() as redirected_out:
                rebuild_result = rebuild(backup_root)
            self.assertEqual(
                rebuild_result,
                RebuildResult(
                    process_count=2,
                    process_size=2000,
                    added_size_count=0,
                    added_hash_count=0,
                    error_count=0,
                ),
            )
            # No new hash of size entries, just the new file:
            self.assertEqual(
                sorted_rglob_files(backup_root),
                [
                    '.phlb/hash-lookup/bb/c4/bbc4de2ca238d1ec41fb622b75b5cf7d31a6d2ac92405043dd8f8220364fefc8',
                    '.phlb/size-lookup/10/00/1000',
                    'source-name/2026-01-15-181709/file1.txt',
                    'source-name/2026-01-15-181709/same_content.txt',
                ],
            )
            self.assertEqual(redirected_out.stderr, '')

            #######################################################################################
            # Test error handling

            def rebuild_one_file_mock(*, entry, **kwargs):
                if entry.name == 'file1.txt':
                    raise IOError('Bam!')
                return rebuild_one_file(entry=entry, **kwargs)

            with (
                self.assertLogs('PyHardLinkBackup', level=logging.ERROR) as logs,
                RedirectOut() as redirected_out,
                patch.object(rebuild_databases, 'rebuild_one_file', rebuild_one_file_mock),
            ):
                rebuild_result = rebuild(backup_root)
            logs = ''.join(logs.output)
            self.assertIn(f'Backup {snapshot_path}/file1.txt OSError: Bam!\n', logs)
            self.assertIn('\nTraceback (most recent call last):\n', logs)
            self.assertEqual(redirected_out.stderr, '')

            self.assertEqual(
                rebuild_result,
                RebuildResult(
                    process_count=1,
                    process_size=1000,
                    added_size_count=0,
                    added_hash_count=0,
                    error_count=1,  # <<< one file caused error
                ),
            )
