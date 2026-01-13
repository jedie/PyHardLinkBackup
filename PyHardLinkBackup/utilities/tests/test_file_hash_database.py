import logging
import tempfile
import textwrap
from pathlib import Path
from unittest import TestCase

from bx_py_utils.path import assert_is_dir
from bx_py_utils.test_utils.assertion import assert_text_equal

from PyHardLinkBackup.utilities.file_hash_database import FileHashDatabase, HashAlreadyExistsError
from PyHardLinkBackup.utilities.filesystem import iter_scandir_files


class TemporaryFileHashDatabase(tempfile.TemporaryDirectory):
    def __enter__(self) -> FileHashDatabase:
        temp_dir = super().__enter__()
        backup_root = Path(temp_dir)

        phlb_conf_dir = backup_root / '.phlb'
        phlb_conf_dir.mkdir()

        hash_db = FileHashDatabase(backup_root=backup_root, phlb_conf_dir=phlb_conf_dir)
        return hash_db


def get_hash_db_filenames(hash_db: FileHashDatabase) -> list[str]:
    return sorted(
        str(Path(entry.path).relative_to(hash_db.base_path))
        for entry in iter_scandir_files(hash_db.base_path, excludes=set())
    )


def get_hash_db_info(backup_root: Path) -> str:
    db_base_path = backup_root / '.phlb' / 'hash-lookup'
    assert_is_dir(db_base_path)

    lines = []
    for entry in iter_scandir_files(db_base_path, excludes=set()):
        hash_path = Path(entry.path)
        rel_path = hash_path.relative_to(db_base_path)
        rel_file_path = hash_path.read_text()
        lines.append(f'{str(rel_path)[:20]}… -> {rel_file_path}')
    return '\n'.join(sorted(lines))


def assert_hash_db_info(backup_root: Path, expected: str):
    expected = textwrap.dedent(expected).strip()
    actual = get_hash_db_info(backup_root)
    assert_text_equal(
        actual,
        expected,
        msg=f'FileHashDatabase info does not match as expected.\n\n{actual}\n\n',
    )


class FileHashDatabaseTestCase(TestCase):
    def test_happy_path(self):
        with TemporaryFileHashDatabase() as hash_db:
            self.assertIsInstance(hash_db, FileHashDatabase)

            backup_root_path = hash_db.backup_root
            assert_is_dir(backup_root_path)

            test_path = hash_db._get_hash_path('12345678abcdef')
            self.assertEqual(test_path, hash_db.base_path / '12' / '34' / '12345678abcdef')

            file_a_path = backup_root_path / 'rel/path/to/file-A'
            file_a_path.parent.mkdir(parents=True, exist_ok=True)
            file_a_path.touch()

            self.assertIs(hash_db.get('12345678abcdef'), None)
            hash_db['12345678abcdef'] = file_a_path
            self.assertEqual(hash_db.get('12345678abcdef'), file_a_path)
            self.assertEqual(
                get_hash_db_filenames(hash_db),
                ['12/34/12345678abcdef'],
            )

            ########################################################################################
            # Another instance using the same directory:

            another_hash_db = FileHashDatabase(
                backup_root=hash_db.backup_root,
                phlb_conf_dir=hash_db.base_path.parent,
            )
            self.assertEqual(another_hash_db.get('12345678abcdef'), file_a_path)
            self.assertIs(another_hash_db.get('12abcd345678abcdef'), None)

            file_b_path = backup_root_path / 'rel/path/to/file-B'
            file_b_path.parent.mkdir(parents=True, exist_ok=True)
            file_b_path.touch()

            another_hash_db['12abcd345678abcdef'] = file_b_path
            self.assertEqual(another_hash_db.get('12abcd345678abcdef'), file_b_path)
            self.assertEqual(
                get_hash_db_filenames(another_hash_db),
                [
                    '12/34/12345678abcdef',
                    '12/ab/12abcd345678abcdef',
                ],
            )

            assert_hash_db_info(
                backup_root=hash_db.backup_root,
                expected="""
                    12/34/12345678abcdef… -> rel/path/to/file-A
                    12/ab/12abcd345678ab… -> rel/path/to/file-B
                """,
            )

            ########################################################################################
            # Deny "overwrite" of existing hash:

            with self.assertRaises(HashAlreadyExistsError):
                hash_db['12abcd345678abcdef'] = 'foo/bar/baz'  # already exists!

            ########################################################################################
            # Don't use stale entries pointing to missing files:

            self.assertEqual(hash_db.get('12345678abcdef'), file_a_path)
            file_a_path.unlink()

            """DocWrite: README.md ## FileHashDatabase - Missing hardlink target file
            We check if the hardlink source file still exists. If not, we remove the hash entry from the database.
            A warning is logged in this case."""
            with self.assertLogs(level=logging.WARNING) as logs:
                self.assertIs(hash_db.get('12345678abcdef'), None)
            self.assertIn('Hash database entry found, but file does not exist', ''.join(logs.output))
            assert_hash_db_info(
                backup_root=hash_db.backup_root,
                expected="""
                    12/ab/12abcd345678ab… -> rel/path/to/file-B
                """,
            )
