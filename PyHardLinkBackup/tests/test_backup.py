import datetime
import logging
import os
import textwrap
import unittest
import zlib
from collections.abc import Iterable
from pathlib import Path
from unittest.mock import patch

from bx_py_utils.path import assert_is_file
from bx_py_utils.test_utils.assertion import assert_text_equal
from bx_py_utils.test_utils.datetime import parse_dt
from bx_py_utils.test_utils.log_utils import NoLogs
from bx_py_utils.test_utils.redirect import RedirectOut
from freezegun import freeze_time
from tabulate import tabulate

from PyHardLinkBackup.backup import BackupResult, backup_tree
from PyHardLinkBackup.constants import CHUNK_SIZE
from PyHardLinkBackup.logging_setup import DEFAULT_LOG_FILE_LEVEL, LoggingManager, LogLevelLiteral
from PyHardLinkBackup.tests.test_compare_backup import assert_compare_backup
from PyHardLinkBackup.utilities.file_size_database import FileSizeDatabase
from PyHardLinkBackup.utilities.filesystem import copy_and_hash, iter_scandir_files
from PyHardLinkBackup.utilities.rich_utils import DisplayFileTreeProgress, NoopProgress
from PyHardLinkBackup.utilities.tests.test_file_hash_database import assert_hash_db_info
from PyHardLinkBackup.utilities.tests.unittest_utilities import (
    CollectOpenFiles,
    PyHardLinkBackupTestCaseMixin,
)


class SortedIterScandirFiles:
    """
    Important for stable tests: os.scandir() does not guarantee any order of the returned entries.
    This class wraps iter_scandir_files() and yields the entries sorted by name.
    """

    def __init__(self, path: Path, excludes: set):
        self.path = path
        self.excludes = excludes

    def __enter__(self):
        return self

    def __iter__(self) -> Iterable[os.DirEntry]:
        scandir_iterator = iter_scandir_files(self.path, self.excludes)
        yield from sorted(scandir_iterator, key=lambda e: e.name)

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def set_file_times(path: Path, dt: datetime.datetime):
    # move dt to UTC if it has timezone info:
    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    fixed_time = dt.timestamp()
    with NoLogs(logger_name=''):
        for entry in iter_scandir_files(path, excludes=set()):
            try:
                os.utime(entry.path, (fixed_time, fixed_time))
            except FileNotFoundError:
                # e.g.: broken symlink ;)
                pass


def _fs_tree_overview(root: Path) -> str:
    lines = []
    for entry in iter_scandir_files(root, excludes=set()):
        file_path = Path(entry.path)
        try:
            file_stat = entry.stat()
        except FileNotFoundError:
            crc32 = '-'
            nlink = '-'
            size = '-'
            birthtime = '-'
        else:
            is_log_file = entry.name.endswith('-backup.log') or entry.name.endswith('-summary.txt')
            if is_log_file:
                # flaky content!
                crc32 = '<mock>'
                size = '<mock>'
            else:
                crc32 = zlib.crc32(file_path.read_bytes())
                crc32 = f'{crc32:08x}'
                size = file_stat.st_size

            nlink = file_stat.st_nlink

            if entry.name == 'SHA256SUMS' or is_log_file:
                birthtime = '<mock>'
            else:
                birthtime = getattr(file_stat, 'st_birthtime', file_stat.st_mtime)
                birthtime = datetime.datetime.fromtimestamp(birthtime).strftime('%H:%M:%S')

        if entry.is_symlink():
            file_type = 'symlink'
        elif nlink > 1:
            file_type = 'hardlink'
        else:
            file_type = 'file'

        lines.append(
            [
                str(file_path.relative_to(root)),
                birthtime,
                file_type,
                nlink,
                size,
                crc32,
            ]
        )

    result = tabulate(sorted(lines), headers=['path', 'birthtime', 'type', 'nlink', 'size', 'CRC32'], tablefmt='plain')
    return result


def assert_fs_tree_overview(root: Path, expected_overview: str):
    expected_overview = textwrap.dedent(expected_overview).strip()
    actual_overview = _fs_tree_overview(root)
    assert_text_equal(
        actual_overview,
        expected_overview,
        msg=f'Filesystem tree overview does not match expected overview.\n\n{actual_overview}\n\n',
    )


class BackupTreeTestCase(
    PyHardLinkBackupTestCaseMixin,
    # TODO: OutputMustCapturedTestCaseMixin,
    unittest.TestCase,
):
    def create_backup(
        self,
        *,
        time_to_freeze: str,
        log_file_level: LogLevelLiteral = DEFAULT_LOG_FILE_LEVEL,
    ):
        # FIXME: freezegun doesn't handle this, see: https://github.com/spulec/freezegun/issues/392
        # Set modification times to a fixed time for easier testing:
        set_file_times(self.src_root, dt=parse_dt('2026-01-01T12:00:00+0000'))

        with (
            patch('PyHardLinkBackup.backup.iter_scandir_files', SortedIterScandirFiles),
            freeze_time(time_to_freeze, auto_tick_seconds=0),
            RedirectOut() as redirected_out,
        ):
            result = backup_tree(
                src_root=self.src_root,
                backup_root=self.backup_root,
                excludes=('.cache',),
                log_manager=LoggingManager(
                    console_level='info',
                    file_level=log_file_level,
                ),
            )

        return redirected_out, result

    def test_happy_path(self):
        file1_path = self.src_root / 'file2.txt'
        file1_path.write_text('This is file 1')

        (self.src_root / 'symlink2file1').symlink_to(file1_path)
        os.link(file1_path, self.src_root / 'hardlink2file1')

        sub_dir = self.src_root / 'subdir'
        sub_dir.mkdir()
        (sub_dir / 'file.txt').write_text('This is file in subdir')

        # Only files bigger than MIN_SIZE will be considered for hardlinking:
        (self.src_root / 'min_sized_file1.bin').write_bytes(b'X' * FileSizeDatabase.MIN_SIZE)

        # Same content and big enough to be considered for hardlinking:
        (self.src_root / 'min_sized_file2.bin').write_bytes(b'X' * FileSizeDatabase.MIN_SIZE)

        # Larger then CHUNK_SIZE file will be handled differently:
        (self.src_root / 'large_file1.bin').write_bytes(b'Y' * (CHUNK_SIZE + 1))

        excluded_dir = self.src_root / '.cache'
        excluded_dir.mkdir()
        (excluded_dir / 'tempfile.tmp').write_text('Temporary file that should be excluded')

        #######################################################################################
        # Create first backup:

        redirected_out, result = self.create_backup(time_to_freeze='2026-01-01T12:34:56Z')

        self.assertEqual(redirected_out.stderr, '')
        self.assertIn('Backup complete', redirected_out.stdout)
        backup_dir = result.backup_dir
        self.assertEqual(
            str(Path(backup_dir).relative_to(self.temp_path)),
            'backups/source/2026-01-01-123456',
        )
        log_file = result.log_file
        self.assertEqual(
            str(Path(log_file).relative_to(self.temp_path)),
            'backups/source/2026-01-01-123456-backup.log',
        )
        self.assertEqual(
            result,
            BackupResult(
                backup_dir=backup_dir,
                log_file=log_file,
                backup_count=7,
                backup_size=67110929,
                symlink_files=1,
                hardlinked_files=1,
                hardlinked_size=1000,
                copied_files=5,
                copied_size=67109915,
                copied_small_files=3,
                copied_small_size=50,
                error_count=0,
            ),
            redirected_out.stdout,
        )

        # The sources:
        with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG):
            assert_fs_tree_overview(
                root=self.src_root,
                expected_overview="""
                    path                 birthtime    type        nlink      size  CRC32
                    .cache/tempfile.tmp  12:00:00     file            1        38  41d7a2c9
                    file2.txt            12:00:00     hardlink        2        14  8a11514a
                    hardlink2file1       12:00:00     hardlink        2        14  8a11514a
                    large_file1.bin      12:00:00     file            1  67108865  9671eaac
                    min_sized_file1.bin  12:00:00     file            1      1000  f0d93de4
                    min_sized_file2.bin  12:00:00     file            1      1000  f0d93de4
                    subdir/file.txt      12:00:00     file            1        22  c0167e63
                    symlink2file1        12:00:00     symlink         2        14  8a11514a
                """,
            )
        # The backup:
        # * /.cache/ -> excluded
        # * min_sized_file1.bin and min_sized_file2.bin -> hardlinked
        with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG):
            assert_fs_tree_overview(
                root=backup_dir,
                expected_overview="""
                    path                 birthtime    type        nlink      size  CRC32
                    SHA256SUMS           <mock>       file            1       411  b02da51e
                    file2.txt            12:00:00     file            1        14  8a11514a
                    hardlink2file1       12:00:00     file            1        14  8a11514a
                    large_file1.bin      12:00:00     file            1  67108865  9671eaac
                    min_sized_file1.bin  12:00:00     hardlink        2      1000  f0d93de4
                    min_sized_file2.bin  12:00:00     hardlink        2      1000  f0d93de4
                    subdir/SHA256SUMS    <mock>       file            1        75  1af5ecc7
                    subdir/file.txt      12:00:00     file            1        22  c0167e63
                    symlink2file1        12:00:00     symlink         2        14  8a11514a
                """,
            )

        # Let's check our FileHashDatabase:
        with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG):
            assert_hash_db_info(
                backup_root=self.backup_root,
                expected="""
                    bb/c4/bbc4de2ca238d1… -> source/2026-01-01-123456/min_sized_file1.bin
                    e6/37/e6374ac11d9049… -> source/2026-01-01-123456/large_file1.bin
                """,
            )

        #######################################################################################
        # Compare the backup

        assert_compare_backup(
            test_case=self,
            src_root=self.src_root,
            backup_root=self.backup_root,
            excludes=('.cache',),
            excpected_last_timestamp='2026-01-01-123456',  # Freezed time, see above
            excpected_total_file_count=7,
            excpected_successful_file_count=7,
            excpected_error_count=0,
        )

        #######################################################################################
        # Backup again with new added files:

        # New small file with different size and different content:
        (self.src_root / 'small_file_newA.txt').write_text('A new file')

        # Add small file that size exists, but has different content:
        (self.src_root / 'small_file_newB.txt').write_text('This is file 2')

        # Bigger file with new size and new content:
        (self.src_root / 'min_sized_file_newA.bin').write_bytes(b'A' * (FileSizeDatabase.MIN_SIZE + 1))

        # Bigger file with existing size, but different content:
        (self.src_root / 'min_sized_file_newB.bin').write_bytes(b'B' * FileSizeDatabase.MIN_SIZE)

        # Add a larger then CHUNK_SIZE file with same existing size, but different content:
        (self.src_root / 'large_file2.bin').write_bytes(b'Y' * (CHUNK_SIZE + 1))

        #######################################################################################
        # Backup the second time:

        redirected_out, result = self.create_backup(time_to_freeze='2026-01-02T12:34:56Z')

        self.assertEqual(redirected_out.stderr, '')
        self.assertIn('Backup complete', redirected_out.stdout)
        backup_dir = result.backup_dir
        self.assertEqual(
            str(Path(backup_dir).relative_to(self.temp_path)),
            'backups/source/2026-01-02-123456',
        )
        # The second backup:
        # * /.cache/ -> excluded
        # * min_sized_file1.bin and min_sized_file2.bin -> hardlinked
        with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG):
            assert_fs_tree_overview(
                root=backup_dir,
                expected_overview="""
                    path                     birthtime    type        nlink      size  CRC32
                    SHA256SUMS               <mock>       file            1       845  6596856a
                    file2.txt                12:00:00     file            1        14  8a11514a
                    hardlink2file1           12:00:00     file            1        14  8a11514a
                    large_file1.bin          12:00:00     hardlink        3  67108865  9671eaac
                    large_file2.bin          12:00:00     hardlink        3  67108865  9671eaac
                    min_sized_file1.bin      12:00:00     hardlink        4      1000  f0d93de4
                    min_sized_file2.bin      12:00:00     hardlink        4      1000  f0d93de4
                    min_sized_file_newA.bin  12:00:00     file            1      1001  a48f0e33
                    min_sized_file_newB.bin  12:00:00     file            1      1000  7d9c564d
                    small_file_newA.txt      12:00:00     file            1        10  76d1acf1
                    small_file_newB.txt      12:00:00     file            1        14  131800f0
                    subdir/SHA256SUMS        <mock>       file            1        75  1af5ecc7
                    subdir/file.txt          12:00:00     file            1        22  c0167e63
                    symlink2file1            12:00:00     symlink         2        14  8a11514a
                """,
            )
        self.assertEqual(
            result,
            BackupResult(
                backup_dir=backup_dir,
                log_file=result.log_file,
                backup_count=12,
                backup_size=134221819,
                symlink_files=1,
                hardlinked_files=4,
                hardlinked_size=134219730,
                copied_files=7,
                copied_size=2075,
                copied_small_files=5,
                copied_small_size=74,
                error_count=0,
            ),
            redirected_out.stdout,
        )

        # The FileHashDatabase remains the same:
        with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG):
            assert_hash_db_info(
                backup_root=self.backup_root,
                expected="""
                    23/d2/23d2ce40d26211… -> source/2026-01-02-123456/min_sized_file_newA.bin
                    9a/56/9a567077114134… -> source/2026-01-02-123456/min_sized_file_newB.bin
                    bb/c4/bbc4de2ca238d1… -> source/2026-01-01-123456/min_sized_file1.bin
                    e6/37/e6374ac11d9049… -> source/2026-01-01-123456/large_file1.bin
                """,
            )

        #######################################################################################
        # Compare the backup

        assert_compare_backup(
            test_case=self,
            src_root=self.src_root,
            backup_root=self.backup_root,
            excludes=('.cache',),
            excpected_last_timestamp='2026-01-02-123456',  # Freezed time, see above
            excpected_total_file_count=12,
            excpected_successful_file_count=12,
            excpected_error_count=0,
        )

        #######################################################################################
        # Don't create broken hardlinks!

        """DocWrite: README.md ## FileHashDatabase - Missing hardlink target file
        If a hardlink source from a old backup is missing, we cannot create a hardlink to it.
        But it still works to hardlink same files within the current backup.
        """

        # Let's remove one of the files used for hardlinking from the first backup:
        min_sized_file1_bak_path = self.backup_root / 'source/2026-01-01-123456/min_sized_file1.bin'
        assert_is_file(min_sized_file1_bak_path)
        min_sized_file1_bak_path.unlink()

        # Backup again:
        redirected_out, result = self.create_backup(time_to_freeze='2026-01-03T12:34:56Z')

        self.assertEqual(redirected_out.stderr, '')
        self.assertIn('Backup complete', redirected_out.stdout)
        backup_dir = result.backup_dir

        # Note: min_sized_file1.bin and min_sized_file2.bin are hardlinked,
        # but not with the first backup anymore! So it's only nlink=2 now!
        with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG):
            assert_fs_tree_overview(
                root=backup_dir,
                expected_overview="""
                    path                     birthtime    type        nlink      size  CRC32
                    SHA256SUMS               <mock>       file            1       845  6596856a
                    file2.txt                12:00:00     file            1        14  8a11514a
                    hardlink2file1           12:00:00     file            1        14  8a11514a
                    large_file1.bin          12:00:00     hardlink        5  67108865  9671eaac
                    large_file2.bin          12:00:00     hardlink        5  67108865  9671eaac
                    min_sized_file1.bin      12:00:00     hardlink        2      1000  f0d93de4
                    min_sized_file2.bin      12:00:00     hardlink        2      1000  f0d93de4
                    min_sized_file_newA.bin  12:00:00     hardlink        2      1001  a48f0e33
                    min_sized_file_newB.bin  12:00:00     hardlink        2      1000  7d9c564d
                    small_file_newA.txt      12:00:00     file            1        10  76d1acf1
                    small_file_newB.txt      12:00:00     file            1        14  131800f0
                    subdir/SHA256SUMS        <mock>       file            1        75  1af5ecc7
                    subdir/file.txt          12:00:00     file            1        22  c0167e63
                    symlink2file1            12:00:00     symlink         2        14  8a11514a
                """,
            )

        self.assertEqual(
            result,
            BackupResult(
                backup_dir=backup_dir,
                log_file=result.log_file,
                backup_count=12,
                backup_size=134221819,
                symlink_files=1,
                hardlinked_files=5,
                hardlinked_size=134220731,
                copied_files=6,
                copied_size=1074,
                copied_small_files=5,
                copied_small_size=74,
                error_count=0,
            ),
        )

        # Note: min_sized_file1.bin is now from the 2026-01-03 backup!
        self.assertEqual(backup_dir.name, '2026-01-03-123456')  # Latest backup dir name
        with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG):
            assert_hash_db_info(
                backup_root=self.backup_root,
                expected="""
                    23/d2/23d2ce40d26211… -> source/2026-01-02-123456/min_sized_file_newA.bin
                    9a/56/9a567077114134… -> source/2026-01-02-123456/min_sized_file_newB.bin
                    bb/c4/bbc4de2ca238d1… -> source/2026-01-03-123456/min_sized_file1.bin
                    e6/37/e6374ac11d9049… -> source/2026-01-01-123456/large_file1.bin
                """,
            )

        #######################################################################################
        # Compare the backup

        assert_compare_backup(
            test_case=self,
            src_root=self.src_root,
            backup_root=self.backup_root,
            excludes=('.cache',),
            excpected_last_timestamp='2026-01-03-123456',  # Freezed time, see above
            excpected_total_file_count=12,
            excpected_successful_file_count=12,
            excpected_error_count=0,
        )

    def test_symlink(self):
        source_file_path = self.src_root / 'source_file.txt'
        source_file_path.write_text('File in the "source" directory.')

        symlink2source_file_path = self.src_root / 'symlink2source'
        symlink2source_file_path.symlink_to(source_file_path)
        self.assertEqual(symlink2source_file_path.read_text(), 'File in the "source" directory.')

        outside_file_path = self.temp_path / 'outside_file.txt'
        outside_file_path.write_text('File outside the "source" directory!')

        symlink2outside_file_path = self.src_root / 'symlink2outside'
        symlink2outside_file_path.symlink_to(outside_file_path)
        self.assertEqual(symlink2outside_file_path.read_text(), 'File outside the "source" directory!')

        broken_symlink_path = self.src_root / 'broken_symlink'
        broken_symlink_path.symlink_to(self.temp_path / 'not/existing/file.txt')
        broken_symlink_path.is_symlink()

        #######################################################################################
        # Create first backup:

        redirected_out, result = self.create_backup(time_to_freeze='2026-01-01T12:34:56Z')
        self.assertEqual(redirected_out.stderr, '')
        self.assertIn('Backup complete', redirected_out.stdout)
        backup_dir1 = result.backup_dir
        self.assertEqual(
            str(Path(backup_dir1).relative_to(self.temp_path)),
            'backups/source/2026-01-01-123456',
        )

        with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG):
            """DocWrite: README.md # PyHardLinkBackup - Notes
            A log file is stored in the backup directory. e.g.:
            * `backups/source/2026-01-01-123456-backup.log`

            A finished backup also creates a summary file. e.g.:
            * `backups/source/2026-01-01-123456-summary.txt`
            """
            assert_fs_tree_overview(
                root=self.temp_path,  # The complete overview os source + backup and outside file
                expected_overview="""
                    path                                              birthtime    type     nlink    size    CRC32
                    backups/source/2026-01-01-123456-backup.log       <mock>       file     1        <mock>  <mock>
                    backups/source/2026-01-01-123456-summary.txt      <mock>       file     1        <mock>  <mock>
                    backups/source/2026-01-01-123456/SHA256SUMS       <mock>       file     1        82      c03fd60e
                    backups/source/2026-01-01-123456/broken_symlink   -            symlink  -        -       -
                    backups/source/2026-01-01-123456/source_file.txt  12:00:00     file     1        31      9309a10c
                    backups/source/2026-01-01-123456/symlink2outside  12:00:00     symlink  1        36      24b5bf4c
                    backups/source/2026-01-01-123456/symlink2source   12:00:00     symlink  1        31      9309a10c
                    outside_file.txt                                  12:00:00     file     1        36      24b5bf4c
                    source/broken_symlink                             -            symlink  -        -       -
                    source/source_file.txt                            12:00:00     file     1        31      9309a10c
                    source/symlink2outside                            12:00:00     symlink  1        36      24b5bf4c
                    source/symlink2source                             12:00:00     symlink  1        31      9309a10c
                """,
            )

        self.assertEqual(
            result,
            BackupResult(
                backup_dir=backup_dir1,
                log_file=result.log_file,
                backup_count=4,
                backup_size=98,
                symlink_files=3,
                hardlinked_files=0,
                hardlinked_size=0,
                copied_files=1,
                copied_size=31,
                copied_small_files=1,
                copied_small_size=31,
                error_count=0,
            ),
        )

        """DocWrite: README.md ## backup implementation - Symlinks
        Symlinks are copied as symlinks in the backup."""
        self.assertEqual(
            (backup_dir1 / 'symlink2outside').read_text(),
            'File outside the "source" directory!',
        )
        self.assertEqual(
            (backup_dir1 / 'symlink2source').read_text(),
            'File in the "source" directory.',
        )
        self.assertEqual((backup_dir1 / 'symlink2outside').readlink(), outside_file_path)
        self.assertEqual((backup_dir1 / 'symlink2source').readlink(), source_file_path)

        """DocWrite: README.md ## backup implementation - Symlinks
        Symlinks are not stored in our FileHashDatabase, because they are not considered for hardlinking."""
        with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG):
            assert_hash_db_info(backup_root=self.backup_root, expected='')

        #######################################################################################
        # Compare the backup

        assert_compare_backup(
            test_case=self,
            src_root=self.src_root,
            backup_root=self.backup_root,
            std_out_parts=(
                'Compare completed.',
                'broken_symlink',  # <<< the error we expect
            ),
            excludes=('.cache',),
            excpected_last_timestamp='2026-01-01-123456',  # Freezed time, see above
            excpected_total_file_count=3,
            excpected_successful_file_count=3,
            excpected_error_count=1,  # One broken symlink
        )

    def test_error_handling(self):
        (self.src_root / 'file1.txt').write_text('File 1')
        (self.src_root / 'file2.txt').write_text('File 2')
        (self.src_root / 'file3.txt').write_text('File 3')

        def mocked_copy_and_hash(src: Path, dst: Path, progress: DisplayFileTreeProgress, total_size: int):
            file_hash = copy_and_hash(src, dst, NoopProgress(), total_size)
            if src.name == 'file2.txt':
                raise PermissionError('Bam!')
            return file_hash

        with (
            patch('PyHardLinkBackup.backup.copy_and_hash', mocked_copy_and_hash),
            CollectOpenFiles(self.temp_path) as collector,
        ):
            redirected_out, result = self.create_backup(time_to_freeze='2026-01-01T12:34:56Z')
        self.assertEqual(
            collector.opened_for_read,
            [
                'r backups/.phlb_test_link',
                'rb source/file1.txt',
                'rb source/file2.txt',
                'rb source/file3.txt',
            ],
        )
        self.assertEqual(
            collector.opened_for_write,
            [
                'w backups/.phlb_test',
                'a backups/source/2026-01-01-123456-backup.log',
                'wb backups/source/2026-01-01-123456/file1.txt',
                'a backups/source/2026-01-01-123456/SHA256SUMS',
                'wb backups/source/2026-01-01-123456/file2.txt',
                'wb backups/source/2026-01-01-123456/file3.txt',
                'a backups/source/2026-01-01-123456/SHA256SUMS',
                'w backups/source/2026-01-01-123456-summary.txt',
            ],
        )
        self.assertEqual(redirected_out.stderr, '')
        self.assertIn('Backup complete', redirected_out.stdout)
        self.assertIn('Errors during backup:', redirected_out.stdout)

        log_file = result.log_file
        assert_is_file(log_file)
        self.assertEqual(str(log_file), f'{self.temp_path}/backups/source/2026-01-01-123456-backup.log')
        logs = log_file.read_text()
        self.assertIn(
            f'Backup {self.src_root / "file2.txt"} PermissionError: Bam!\n',
            logs,
        )
        self.assertIn('\nTraceback (most recent call last):\n', logs)
        self.assertIn(
            f'Removing incomplete file {self.temp_path}/backups/source/2026-01-01-123456/file2.txt'
            ' due to error: Bam!\n',
            logs,
        )
        self.assertEqual(
            result,
            BackupResult(
                backup_dir=result.backup_dir,
                log_file=log_file,
                backup_count=3,
                backup_size=18,
                symlink_files=0,
                hardlinked_files=0,
                hardlinked_size=0,
                copied_files=2,
                copied_size=12,
                copied_small_files=2,
                copied_small_size=12,
                error_count=1,
            ),
        )
        with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG):
            assert_fs_tree_overview(
                root=result.backup_dir,
                expected_overview="""
                    path        birthtime    type      nlink    size  CRC32
                    SHA256SUMS  <mock>       file          1     152  563342a4
                    file1.txt   12:00:00     file          1       6  07573806
                    file3.txt   12:00:00     file          1       6  e959592a
                """,  # file2.txt is missing!
            )

        #######################################################################################
        # Compare the backup

        assert_compare_backup(
            test_case=self,
            src_root=self.src_root,
            backup_root=self.backup_root,
            std_out_parts=(
                'Compare completed.',
                'file2.txt not found',  # <<< the error we expect
            ),
            excludes=('.cache',),
            excpected_last_timestamp='2026-01-01-123456',  # Freezed time, see above
            excpected_total_file_count=3,
            excpected_successful_file_count=2,
            excpected_error_count=0,
        )

    def test_skip_sha256sums_file(self):
        (self.src_root / 'SHA256SUMS').write_text('dummy hash content')
        (self.src_root / 'file.txt').write_text('normal file')

        with CollectOpenFiles(self.temp_path) as collector:
            redirected_out, result = self.create_backup(
                time_to_freeze='2026-01-01T12:34:56Z',
                log_file_level='debug',  # Skip SHA256SUMS is logged at DEBUG level
            )
        self.assertEqual(
            collector.opened_for_read,
            [
                'r backups/.phlb_test_link',
                'rb source/file.txt',
            ],
        )
        self.assertEqual(
            collector.opened_for_write,
            [
                'w backups/.phlb_test',
                'a backups/source/2026-01-01-123456-backup.log',
                'wb backups/source/2026-01-01-123456/file.txt',
                'a backups/source/2026-01-01-123456/SHA256SUMS',
                'w backups/source/2026-01-01-123456-summary.txt',
            ],
        )
        backup_dir = result.backup_dir

        with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG):
            assert_fs_tree_overview(
                root=backup_dir,
                expected_overview="""
                    path        birthtime    type      nlink    size  CRC32
                    SHA256SUMS  <mock>       file          1      75  9570b1e4
                    file.txt    12:00:00     file          1      11  e29f436e
                """,
            )

        self.assertEqual(
            (backup_dir / 'SHA256SUMS').read_text(),
            # Not the dummy content -> the real SHA256SUMS file content:
            '87f644d525b412d6162932d06db1bc06aaa0508374badc861e40ad85b0e01412  file.txt\n',
        )

        self.assertIn(
            'Skip existing SHA256SUMS file',
            result.log_file.read_text(),
        )

    def test_large_file_handling(self):
        (self.src_root / 'large_fileA.txt').write_bytes(b'A' * 1001)

        with patch('PyHardLinkBackup.backup.CHUNK_SIZE', 1000), CollectOpenFiles(self.temp_path) as collector:
            redirected_out, result = self.create_backup(time_to_freeze='2026-01-11T12:34:56Z')
        self.assertEqual(
            collector.opened_for_read,
            [
                'r backups/.phlb_test_link',
                'rb source/large_fileA.txt',
            ],
        )
        self.assertEqual(
            collector.opened_for_write,
            [
                'w backups/.phlb_test',
                'a backups/source/2026-01-11-123456-backup.log',
                'wb backups/source/2026-01-11-123456/large_fileA.txt',
                'w backups/.phlb/hash-lookup/23/d2/23d2ce40d26211a9ffe8096fd1f927f2abd094691839d24f88440f7c5168d500',
                'a backups/source/2026-01-11-123456/SHA256SUMS',
                'w backups/source/2026-01-11-123456-summary.txt',
            ],
        )
        backup_dir = result.backup_dir

        with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG):
            assert_fs_tree_overview(
                root=backup_dir,
                expected_overview="""
                    path             birthtime    type      nlink    size  CRC32
                    SHA256SUMS       <mock>       file          1      82  c3dd960b
                    large_fileA.txt  12:00:00     file          1    1001  a48f0e33
                """,
            )

        self.assertEqual(
            (backup_dir / 'SHA256SUMS').read_text(),
            '23d2ce40d26211a9ffe8096fd1f927f2abd094691839d24f88440f7c5168d500  large_fileA.txt\n',
        )

        # Same size, different content -> should be copied again:
        (self.src_root / 'large_fileB.txt').write_bytes(b'B' * 1001)

        with patch('PyHardLinkBackup.backup.CHUNK_SIZE', 1000), CollectOpenFiles(self.temp_path) as collector:
            redirected_out, result = self.create_backup(time_to_freeze='2026-02-22T12:34:56Z')
        self.assertEqual(
            collector.opened_for_read,
            [
                'r backups/.phlb_test_link',
                'rb source/large_fileA.txt',
                'r backups/.phlb/hash-lookup/23/d2/23d2ce40d26211a9ffe8096fd1f927f2abd094691839d24f88440f7c5168d500',
                'rb source/large_fileB.txt',
                'r backups/.phlb/hash-lookup/2a/92/2a925556d3ec9e4258624a324cd9300a9a3d9c86dac6bbbb63071bdb7787afd2',
                'rb source/large_fileB.txt',
            ],
        )
        self.assertEqual(
            collector.opened_for_write,
            [
                'w backups/.phlb_test',
                'a backups/source/2026-02-22-123456-backup.log',
                'a backups/source/2026-02-22-123456/SHA256SUMS',
                'wb backups/source/2026-02-22-123456/large_fileB.txt',
                'w backups/.phlb/hash-lookup/2a/92/2a925556d3ec9e4258624a324cd9300a9a3d9c86dac6bbbb63071bdb7787afd2',
                'a backups/source/2026-02-22-123456/SHA256SUMS',
                'w backups/source/2026-02-22-123456-summary.txt',
            ],
        )
        backup_dir = result.backup_dir

        self.assertEqual(
            (backup_dir / 'large_fileA.txt').read_text()[:50],
            'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',  # ... AAA
        )
        self.assertEqual(
            (backup_dir / 'large_fileB.txt').read_text()[:50],
            'BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB',  # ... BBB
        )

        log_file_content = result.log_file.read_text()
        self.assertIn(
            f'Hardlink duplicate file: {self.temp_path}/backups/source/2026-02-22-123456/large_fileA.txt'
            f' to {self.temp_path}/backups/source/2026-01-11-123456/large_fileA.txt',
            log_file_content,
        )
        self.assertIn(
            f'Copy unique file: {self.temp_path}/source/large_fileB.txt'
            f' to {self.temp_path}/backups/source/2026-02-22-123456/large_fileB.txt',
            log_file_content,
        )

        with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG):
            assert_fs_tree_overview(
                root=self.backup_root / 'source',
                expected_overview="""
                    path                               birthtime    type        nlink  size    CRC32
                    2026-01-11-123456-backup.log       <mock>       file            1  <mock>  <mock>
                    2026-01-11-123456-summary.txt      <mock>       file            1  <mock>  <mock>
                    2026-01-11-123456/SHA256SUMS       <mock>       file            1  82      c3dd960b
                    2026-01-11-123456/large_fileA.txt  12:00:00     hardlink        2  1001    a48f0e33
                    2026-02-22-123456-backup.log       <mock>       file            1  <mock>  <mock>
                    2026-02-22-123456-summary.txt      <mock>       file            1  <mock>  <mock>
                    2026-02-22-123456/SHA256SUMS       <mock>       file            1  164     3130cbcb
                    2026-02-22-123456/large_fileA.txt  12:00:00     hardlink        2  1001    a48f0e33
                    2026-02-22-123456/large_fileB.txt  12:00:00     file            1  1001    42c06e4a
                """,
            )
