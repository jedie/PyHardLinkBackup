import tempfile
from pathlib import Path
from unittest import TestCase

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


class FileHashDatabaseTestCase(TestCase):
    def test_happy_path(self):
        with TemporaryFileHashDatabase() as hash_db:
            self.assertIsInstance(hash_db, FileHashDatabase)

            test_path = hash_db._get_hash_path('12345678abcdef')
            self.assertEqual(test_path, hash_db.base_path / '12' / '34' / '12345678abcdef')

            self.assertIs(hash_db.get('12345678abcdef'), None)
            hash_db['12345678abcdef'] = hash_db.backup_root / 'rel/path/to/file-A'
            self.assertEqual(hash_db.get('12345678abcdef'), hash_db.backup_root / 'rel/path/to/file-A')

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
            self.assertEqual(another_hash_db.get('12345678abcdef'), hash_db.backup_root / 'rel/path/to/file-A')
            self.assertIs(another_hash_db.get('12abcd345678abcdef'), None)
            another_hash_db['12abcd345678abcdef'] = hash_db.backup_root / 'rel/path/to/file-B'
            self.assertEqual(another_hash_db.get('12abcd345678abcdef'), hash_db.backup_root / 'rel/path/to/file-B')
            self.assertEqual(
                get_hash_db_filenames(another_hash_db),
                [
                    '12/34/12345678abcdef',
                    '12/ab/12abcd345678abcdef',
                ],
            )

            ########################################################################################
            # Deny "overwrite" of existing hash:

            with self.assertRaises(HashAlreadyExistsError):
                hash_db['12abcd345678abcdef'] = 'foo/bar/baz'  # already exists!
