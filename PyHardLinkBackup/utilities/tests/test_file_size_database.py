import tempfile
from collections.abc import Iterable
from pathlib import Path
from unittest import TestCase

from PyHardLinkBackup.utilities.file_size_database import FileSizeDatabase
from PyHardLinkBackup.utilities.filesystem import iter_scandir_files


class TemporaryFileSizeDatabase(tempfile.TemporaryDirectory):
    def __enter__(self) -> FileSizeDatabase:
        temp_dir = super().__enter__()
        backup_root = Path(temp_dir)

        phlb_conf_dir = backup_root / '.phlb'
        phlb_conf_dir.mkdir()

        size_db = FileSizeDatabase(phlb_conf_dir=phlb_conf_dir)
        return size_db


def get_size_db_filenames(size_db: FileSizeDatabase) -> Iterable[str]:
    return sorted(
        str(Path(entry.path).relative_to(size_db.base_path))
        for entry in iter_scandir_files(size_db.base_path, excludes=set())
    )


def get_sizes(size_db: FileSizeDatabase) -> Iterable[int]:
    return sorted(int(entry.name) for entry in iter_scandir_files(size_db.base_path, excludes=set()))


class FileSizeDatabaseTestCase(TestCase):
    def test_happy_path(self):
        with TemporaryFileSizeDatabase() as size_db:
            self.assertIsInstance(size_db, FileSizeDatabase)

            test_path1 = size_db._get_size_path(1234)
            self.assertEqual(test_path1, size_db.base_path / '12' / '34' / '1234')

            test_path2 = size_db._get_size_path(567890)
            self.assertEqual(test_path2, size_db.base_path / '56' / '78' / '567890')

            self.assertNotIn(1234, size_db)
            self.assertNotIn(567890, size_db)

            size_db.add(1234)
            self.assertIn(1234, size_db)
            self.assertNotIn(567890, size_db)

            size_db.add(567890)
            self.assertIn(1234, size_db)
            self.assertIn(567890, size_db)

            self.assertEqual(get_sizes(size_db), [1234, 567890])
            self.assertEqual(
                get_size_db_filenames(size_db),
                [
                    '12/34/1234',
                    '56/78/567890',
                ],
            )

            ########################################################################################
            # Another instance using the same directory:

            another_size_db = FileSizeDatabase(phlb_conf_dir=size_db.base_path.parent)
            self.assertEqual(get_sizes(another_size_db), [1234, 567890])
            self.assertEqual(
                get_size_db_filenames(another_size_db),
                [
                    '12/34/1234',
                    '56/78/567890',
                ],
            )

            ########################################################################################
            # "Share" directories:

            for size in (123400001111, 123400002222, 128800003333, 129900004444):
                self.assertNotIn(size, size_db)
                size_db.add(size)
                self.assertIn(size, size_db)

            ########################################################################################
            # Min size is 1000 bytes:

            """DocWrite: README.md ## FileSizeDatabase - minimum file size
            The minimum file size that can be stored in the FileSizeDatabase is 1000 bytes.
            This is because no padding is made for sizes below 1000 bytes, which would
            break the directory structure.
            """
            self.assertEqual(FileSizeDatabase.MIN_SIZE, 1000)
            """DocWrite: README.md ## FileSizeDatabase - minimum file size
            The idea is, that it's more efficient to backup small files directly, instead of
            checking for duplicates via hardlinks. Therefore, small files below this size
            are not tracked in the FileSizeDatabase.
            """

            with self.assertRaises(AssertionError):
                size_db._get_size_path(999)
            with self.assertRaises(AssertionError):
                size_db.add(999)
            with self.assertRaises(AssertionError):
                999 in size_db

            ########################################################################################
            # Check final state:

            self.assertEqual(
                get_size_db_filenames(size_db),
                [
                    '12/34/1234',
                    '12/34/123400001111',
                    '12/34/123400002222',
                    '12/88/128800003333',
                    '12/99/129900004444',
                    '56/78/567890',
                ],
            )
            self.assertEqual(
                get_sizes(size_db),
                [
                    1234,
                    567890,
                    123400001111,
                    123400002222,
                    128800003333,
                    129900004444,
                ],
            )
