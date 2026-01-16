import datetime
import logging
import os
import tempfile
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
from cli_base.cli_tools.test_utils.base_testcases import OutputMustCapturedTestCaseMixin
from freezegun import freeze_time
from tabulate import tabulate

from PyHardLinkBackup.backup import BackupResult, backup_tree
from PyHardLinkBackup.constants import CHUNK_SIZE
from PyHardLinkBackup.logging_setup import DEFAULT_CONSOLE_LOG_LEVEL, DEFAULT_LOG_FILE_LEVEL, LoggingManager
from PyHardLinkBackup.utilities.file_size_database import FileSizeDatabase
from PyHardLinkBackup.utilities.filesystem import copy_and_hash, iter_scandir_files
from PyHardLinkBackup.utilities.tests.test_file_hash_database import assert_hash_db_info


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
            os.utime(entry.path, (fixed_time, fixed_time))


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
    OutputMustCapturedTestCaseMixin,
    unittest.TestCase,
):
    def test_happy_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir).resolve()

            src_root = temp_path / 'source'
            backup_root = temp_path / 'backup'

            src_root.mkdir()
            backup_root.mkdir()

            file1_path = src_root / 'file2.txt'
            file1_path.write_text('This is file 1')

            (src_root / 'symlink2file1').symlink_to(file1_path)
            os.link(file1_path, src_root / 'hardlink2file1')

            sub_dir = src_root / 'subdir'
            sub_dir.mkdir()
            (sub_dir / 'file.txt').write_text('This is file in subdir')

            # Only files bigger than MIN_SIZE will be considered for hardlinking:
            (src_root / 'min_sized_file1.bin').write_bytes(b'X' * FileSizeDatabase.MIN_SIZE)

            # Same content and big enough to be considered for hardlinking:
            (src_root / 'min_sized_file2.bin').write_bytes(b'X' * FileSizeDatabase.MIN_SIZE)

            # Larger then CHUNK_SIZE file will be handled differently:
            (src_root / 'large_file1.bin').write_bytes(b'Y' * (CHUNK_SIZE + 1))

            excluded_dir = src_root / '.cache'
            excluded_dir.mkdir()
            (excluded_dir / 'tempfile.tmp').write_text('Temporary file that should be excluded')

            # FIXME: freezegun doesn't handle this, see: https://github.com/spulec/freezegun/issues/392
            # Set modification times to a fixed time for easier testing:
            set_file_times(src_root, dt=parse_dt('2026-01-01T12:00:00+0000'))

            #######################################################################################
            # Create first backup:

            with (
                patch('PyHardLinkBackup.backup.iter_scandir_files', SortedIterScandirFiles),
                freeze_time('2026-01-01T12:34:56Z', auto_tick_seconds=0),
                RedirectOut() as redirected_out,
            ):
                result = backup_tree(
                    src_root=src_root,
                    backup_root=backup_root,
                    excludes=('.cache',),
                    log_manager=LoggingManager(
                        console_level='info',
                        file_level=DEFAULT_LOG_FILE_LEVEL,
                    ),
                )
            self.assertEqual(redirected_out.stderr, '')
            self.assertIn('Backup complete', redirected_out.stdout)
            backup_dir = result.backup_dir
            self.assertEqual(
                str(Path(backup_dir).relative_to(temp_path)),
                'backup/source/2026-01-01-123456',
            )
            log_file = result.log_file
            self.assertEqual(
                str(Path(log_file).relative_to(temp_path)),
                'backup/source/2026-01-01-123456-backup.log',
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
                    root=src_root,
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
                    backup_root=backup_root,
                    expected="""
                        bb/c4/bbc4de2ca238d1… -> source/2026-01-01-123456/min_sized_file1.bin
                        e6/37/e6374ac11d9049… -> source/2026-01-01-123456/large_file1.bin
                    """,
                )

            #######################################################################################
            # Backup again with new added files:

            # New small file with different size and different content:
            (src_root / 'small_file_newA.txt').write_text('A new file')

            # Add small file that size exists, but has different content:
            (src_root / 'small_file_newB.txt').write_text('This is file 2')

            # Bigger file with new size and new content:
            (src_root / 'min_sized_file_newA.bin').write_bytes(b'A' * (FileSizeDatabase.MIN_SIZE + 1))

            # Bigger file with existing size, but different content:
            (src_root / 'min_sized_file_newB.bin').write_bytes(b'B' * FileSizeDatabase.MIN_SIZE)

            # Add a larger then CHUNK_SIZE file with same existing size, but different content:
            (src_root / 'large_file2.bin').write_bytes(b'Y' * (CHUNK_SIZE + 1))

            # FIXME: freezegun doesn't handle this, see: https://github.com/spulec/freezegun/issues/392
            # Set modification times to a fixed time for easier testing:
            set_file_times(src_root, dt=parse_dt('2026-01-01T12:00:00+0000'))

            with (
                patch('PyHardLinkBackup.backup.iter_scandir_files', SortedIterScandirFiles),
                freeze_time('2026-01-02T12:34:56Z', auto_tick_seconds=0),
                RedirectOut() as redirected_out,
            ):
                result = backup_tree(
                    src_root=src_root,
                    backup_root=backup_root,
                    excludes=('.cache',),
                    log_manager=LoggingManager(
                        console_level='info',
                        file_level=DEFAULT_LOG_FILE_LEVEL,
                    ),
                )
            self.assertEqual(redirected_out.stderr, '')
            self.assertIn('Backup complete', redirected_out.stdout)
            backup_dir = result.backup_dir
            self.assertEqual(
                str(Path(backup_dir).relative_to(temp_path)),
                'backup/source/2026-01-02-123456',
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
                    backup_root=backup_root,
                    expected="""
                        23/d2/23d2ce40d26211… -> source/2026-01-02-123456/min_sized_file_newA.bin
                        9a/56/9a567077114134… -> source/2026-01-02-123456/min_sized_file_newB.bin
                        bb/c4/bbc4de2ca238d1… -> source/2026-01-01-123456/min_sized_file1.bin
                        e6/37/e6374ac11d9049… -> source/2026-01-01-123456/large_file1.bin
                    """,
                )

            #######################################################################################
            # Don't create broken hardlinks!

            """DocWrite: README.md ## FileHashDatabase - Missing hardlink target file
            If a hardlink source from a old backup is missing, we cannot create a hardlink to it.
            But it still works to hardlink same files within the current backup.
            """

            # Let's remove one of the files used for hardlinking from the first backup:
            min_sized_file1_bak_path = backup_root / 'source/2026-01-01-123456/min_sized_file1.bin'
            assert_is_file(min_sized_file1_bak_path)
            min_sized_file1_bak_path.unlink()

            # Backup again:
            with (
                patch('PyHardLinkBackup.backup.iter_scandir_files', SortedIterScandirFiles),
                freeze_time('2026-01-03T12:34:56Z', auto_tick_seconds=0),
                RedirectOut() as redirected_out,
            ):
                result = backup_tree(
                    src_root=src_root,
                    backup_root=backup_root,
                    excludes=('.cache',),
                    log_manager=LoggingManager(
                        console_level=DEFAULT_CONSOLE_LOG_LEVEL,
                        file_level=DEFAULT_LOG_FILE_LEVEL,
                    ),
                )
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
                    error_count=0
                ),
            )

            # Note: min_sized_file1.bin is now from the 2026-01-03 backup!
            self.assertEqual(backup_dir.name, '2026-01-03-123456')  # Latest backup dir name
            with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG):
                assert_hash_db_info(
                    backup_root=backup_root,
                    expected="""
                        23/d2/23d2ce40d26211… -> source/2026-01-02-123456/min_sized_file_newA.bin
                        9a/56/9a567077114134… -> source/2026-01-02-123456/min_sized_file_newB.bin
                        bb/c4/bbc4de2ca238d1… -> source/2026-01-03-123456/min_sized_file1.bin
                        e6/37/e6374ac11d9049… -> source/2026-01-01-123456/large_file1.bin
                    """,
                )

    def test_symlink(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir).resolve()

            src_root = temp_path / 'src'
            backup_root = temp_path / 'bak'

            src_root.mkdir()
            backup_root.mkdir()

            source_file_path = src_root / 'source_file.txt'
            source_file_path.write_text('File in the "source" directory.')

            symlink2source_file_path = src_root / 'symlink2source'
            symlink2source_file_path.symlink_to(source_file_path)
            self.assertEqual(symlink2source_file_path.read_text(), 'File in the "source" directory.')

            outside_file_path = temp_path / 'outside_file.txt'
            outside_file_path.write_text('File outside the "source" directory!')

            symlink2outside_file_path = src_root / 'symlink2outside'
            symlink2outside_file_path.symlink_to(outside_file_path)
            self.assertEqual(symlink2outside_file_path.read_text(), 'File outside the "source" directory!')

            # FIXME: freezegun doesn't handle this, see: https://github.com/spulec/freezegun/issues/392
            # Set modification times to a fixed time for easier testing:
            set_file_times(src_root, dt=parse_dt('2026-01-01T12:00:00+0000'))

            broken_symlink_path = src_root / 'broken_symlink'
            broken_symlink_path.symlink_to(temp_path / 'not/existing/file.txt')
            broken_symlink_path.is_symlink()

            #######################################################################################
            # Create first backup:

            with (
                freeze_time('2026-01-01T12:34:56Z', auto_tick_seconds=0),
                RedirectOut() as redirected_out,
            ):
                result = backup_tree(
                    src_root=src_root,
                    backup_root=backup_root,
                    excludes=(),
                    log_manager=LoggingManager(
                        console_level=DEFAULT_CONSOLE_LOG_LEVEL,
                        file_level=DEFAULT_LOG_FILE_LEVEL,
                    ),
                )
            self.assertEqual(redirected_out.stderr, '')
            self.assertIn('Backup complete', redirected_out.stdout)
            backup_dir1 = result.backup_dir
            self.assertEqual(
                str(Path(backup_dir1).relative_to(temp_path)),
                'bak/src/2026-01-01-123456',
            )

            with self.assertLogs('PyHardLinkBackup', level=logging.DEBUG):
                """DocWrite: README.md # PyHardLinkBackup - Notes
                A log file is stored in the backup directory. e.g.:
                * `bak/src/2026-01-01-123456-backup.log`

                A finished backup also creates a summary file. e.g.:
                * `bak/src/2026-01-01-123456-summary.txt`
                """
                assert_fs_tree_overview(
                    root=temp_path,  # The complete overview os source + backup and outside file
                    expected_overview="""
                        path                                       birthtime    type     nlink    size    CRC32
                        bak/src/2026-01-01-123456-backup.log       <mock>       file     1        <mock>  <mock>
                        bak/src/2026-01-01-123456-summary.txt      <mock>       file     1        <mock>  <mock>
                        bak/src/2026-01-01-123456/SHA256SUMS       <mock>       file     1        82      c03fd60e
                        bak/src/2026-01-01-123456/broken_symlink   -            symlink  -        -       -
                        bak/src/2026-01-01-123456/source_file.txt  12:00:00     file     1        31      9309a10c
                        bak/src/2026-01-01-123456/symlink2outside  12:00:00     symlink  1        36      24b5bf4c
                        bak/src/2026-01-01-123456/symlink2source   12:00:00     symlink  1        31      9309a10c
                        outside_file.txt                           12:00:00     file     1        36      24b5bf4c
                        src/broken_symlink                         -            symlink  -        -       -
                        src/source_file.txt                        12:00:00     file     1        31      9309a10c
                        src/symlink2outside                        12:00:00     symlink  1        36      24b5bf4c
                        src/symlink2source                         12:00:00     symlink  1        31      9309a10c
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
                assert_hash_db_info(backup_root=backup_root, expected='')

    def test_error_handling(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir).resolve()

            src_root = temp_path / 'source'
            backup_root = temp_path / 'backup'

            src_root.mkdir()
            backup_root.mkdir()

            (src_root / 'file1.txt').write_text('File 1')
            (src_root / 'file2.txt').write_text('File 2')
            (src_root / 'file3.txt').write_text('File 3')

            # Set modification times to a fixed time for easier testing:
            set_file_times(src_root, dt=parse_dt('2026-01-01T12:00:00+0000'))

            def mocked_copy_and_hash(src: Path, dst: Path):
                if src.name == 'file2.txt':
                    raise PermissionError('Bam!')
                else:
                    return copy_and_hash(src, dst)

            with (
                patch('PyHardLinkBackup.backup.iter_scandir_files', SortedIterScandirFiles),
                patch('PyHardLinkBackup.backup.copy_and_hash', mocked_copy_and_hash),
                freeze_time('2026-01-01T12:34:56Z', auto_tick_seconds=0),
                RedirectOut() as redirected_out,
            ):
                result = backup_tree(
                    src_root=src_root,
                    backup_root=backup_root,
                    excludes=('.cache',),
                    log_manager=LoggingManager(
                        console_level=DEFAULT_CONSOLE_LOG_LEVEL,
                        file_level=DEFAULT_LOG_FILE_LEVEL,
                    ),
                )
            self.assertEqual(redirected_out.stderr, '')
            self.assertIn('Backup complete', redirected_out.stdout)
            self.assertIn('Errors during backup:', redirected_out.stdout)

            log_file = result.log_file
            assert_is_file(log_file)
            self.assertEqual(str(log_file), f'{temp_path}/backup/source/2026-01-01-123456-backup.log')
            logs = log_file.read_text()
            self.assertIn(
                f'Backup {src_root / "file2.txt"} PermissionError: Bam!\n',
                logs,
            )
            self.assertIn('\nTraceback (most recent call last):\n', logs)
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
