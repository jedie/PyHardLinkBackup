import os
import tempfile
import textwrap
import zlib
from pathlib import Path
from unittest import TestCase

from bx_py_utils.test_utils.assertion import assert_text_equal
from freezegun import freeze_time

from PyHardLinkBackup.backup import BackupResult, backup_tree
from PyHardLinkBackup.constants import CHUNK_SIZE
from PyHardLinkBackup.utilities.file_size_database import FileSizeDatabase
from PyHardLinkBackup.utilities.filesystem import iter_scandir_files


def fs_tree_overview(root: Path) -> str:
    lines = []
    for entry in iter_scandir_files(root, excludes=set()):
        file_path = Path(entry.path)
        crc32 = zlib.crc32(file_path.read_bytes())
        rel_path = file_path.relative_to(root)

        nlink = entry.stat().st_nlink
        if entry.is_symlink():
            file_type = 'symlink'
        elif nlink > 1:
            file_type = 'hardlink'
        else:
            file_type = 'file'

        lines.append(
            f'{str(rel_path):<20} | {file_type:<8} | {nlink=} | {entry.stat().st_size:>8} Bytes | crc32: {crc32:08x}'
        )
    return '\n'.join(sorted(lines))


def assert_fs_tree_overview(root: Path, expected_overview: str):
    expected_overview = textwrap.dedent(expected_overview).strip()
    actual_overview = fs_tree_overview(root)
    assert_text_equal(
        actual_overview,
        expected_overview,
        msg=f'Filesystem tree overview does not match expected overview.\n\n{actual_overview}\n\n',
    )


class BackupTreeTestCase(TestCase):
    def test_happy_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

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
            size_db_min_file = src_root / 'min_sized_file1.bin'
            size_db_min_file.write_bytes(b'X' * FileSizeDatabase.MIN_SIZE)

            # Same content and big enough to be considered for hardlinking:
            size_db_min_file = src_root / 'min_sized_file2.bin'
            size_db_min_file.write_bytes(b'X' * FileSizeDatabase.MIN_SIZE)

            # Larger then CHUNK_SIZE file will be handled differently:
            large_file = src_root / 'large_file.bin'
            large_file.write_bytes(b'Y' * (CHUNK_SIZE + 1))

            excluded_dir = src_root / '.cache'
            excluded_dir.mkdir()
            (excluded_dir / 'tempfile.tmp').write_text('Temporary file that should be excluded')

            #######################################################################################
            # Create first backup:

            with freeze_time('2026-01-01T12:34:56Z', auto_tick_seconds=0):
                result = backup_tree(
                    src_root=src_root,
                    backup_root=backup_root,
                    excludes={'.cache'},
                )
            backup_dir = result.backup_dir
            self.assertEqual(
                str(Path(backup_dir).relative_to(temp_path)),
                'backup/source/20260101_123456',
            )
            self.assertEqual(
                result,
                BackupResult(
                    backup_dir=backup_dir,
                    backup_count=7,
                    backup_size=67110929,
                    symlink_files=1,
                    hardlinked_files=1,
                    hardlinked_size=1000,
                    copied_files=5,
                    copied_size=67109915,
                    copied_small_files=3,
                    copied_small_size=50,
                ),
            )

            # The sources:
            assert_fs_tree_overview(
                root=src_root,
                expected_overview="""
                    .cache/tempfile.tmp  | file     | nlink=1 |       38 Bytes | crc32: 41d7a2c9
                    file2.txt            | hardlink | nlink=2 |       14 Bytes | crc32: 8a11514a
                    hardlink2file1       | hardlink | nlink=2 |       14 Bytes | crc32: 8a11514a
                    large_file.bin       | file     | nlink=1 | 67108865 Bytes | crc32: 9671eaac
                    min_sized_file1.bin  | file     | nlink=1 |     1000 Bytes | crc32: f0d93de4
                    min_sized_file2.bin  | file     | nlink=1 |     1000 Bytes | crc32: f0d93de4
                    subdir/file.txt      | file     | nlink=1 |       22 Bytes | crc32: c0167e63
                    symlink2file1        | symlink  | nlink=2 |       14 Bytes | crc32: 8a11514a
                """,
            )
            # The backup:
            # * /.cache/ -> excluded
            # * min_sized_file1.bin and min_sized_file2.bin -> hardlinked
            assert_fs_tree_overview(
                root=backup_dir,
                expected_overview="""
                    file2.txt            | file     | nlink=1 |       14 Bytes | crc32: 8a11514a
                    hardlink2file1       | file     | nlink=1 |       14 Bytes | crc32: 8a11514a
                    large_file.bin       | file     | nlink=1 | 67108865 Bytes | crc32: 9671eaac
                    min_sized_file1.bin  | hardlink | nlink=2 |     1000 Bytes | crc32: f0d93de4
                    min_sized_file2.bin  | hardlink | nlink=2 |     1000 Bytes | crc32: f0d93de4
                    subdir/file.txt      | file     | nlink=1 |       22 Bytes | crc32: c0167e63
                    symlink2file1        | symlink  | nlink=2 |       14 Bytes | crc32: 8a11514a
                """,
            )

            #######################################################################################
            # Just backup again:

            with freeze_time('2026-01-02T12:34:56Z', auto_tick_seconds=0):
                result = backup_tree(
                    src_root=src_root,
                    backup_root=backup_root,
                    excludes={'.cache'},
                )
            backup_dir = result.backup_dir
            self.assertEqual(
                str(Path(backup_dir).relative_to(temp_path)),
                'backup/source/20260102_123456',
            )
            self.assertEqual(
                result,
                BackupResult(
                    backup_dir=backup_dir,
                    backup_count=7,
                    backup_size=67110929,
                    symlink_files=1,
                    hardlinked_files=3,  # <<< More hardlinks this time!
                    hardlinked_size=67110865,
                    copied_files=3,
                    copied_size=50,
                    copied_small_files=3,
                    copied_small_size=50,
                ),
            )
            # The second backup:
            # * /.cache/ -> excluded
            # * min_sized_file1.bin and min_sized_file2.bin -> hardlinked
            assert_fs_tree_overview(
                root=backup_dir,
                expected_overview="""
                    file2.txt            | file     | nlink=1 |       14 Bytes | crc32: 8a11514a
                    hardlink2file1       | file     | nlink=1 |       14 Bytes | crc32: 8a11514a
                    large_file.bin       | hardlink | nlink=2 | 67108865 Bytes | crc32: 9671eaac
                    min_sized_file1.bin  | hardlink | nlink=4 |     1000 Bytes | crc32: f0d93de4
                    min_sized_file2.bin  | hardlink | nlink=4 |     1000 Bytes | crc32: f0d93de4
                    subdir/file.txt      | file     | nlink=1 |       22 Bytes | crc32: c0167e63
                    symlink2file1        | symlink  | nlink=2 |       14 Bytes | crc32: 8a11514a
                """,
            )
