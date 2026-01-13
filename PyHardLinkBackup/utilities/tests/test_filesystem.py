import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from PyHardLinkBackup.constants import HASH_ALGO
from PyHardLinkBackup.utilities.filesystem import copy_and_hash, hash_file, iter_scandir_files, read_and_hash_file


class TestHashFile(unittest.TestCase):
    def test_hash_file(self):
        self.assertEqual(
            hashlib.new(HASH_ALGO, b'test content').hexdigest(),
            '6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72',
        )
        with tempfile.NamedTemporaryFile() as temp:
            temp_file_path = Path(temp.name)
            temp_file_path.write_bytes(b'test content')

            with self.assertLogs(level='INFO') as logs:
                file_hash = hash_file(temp_file_path)
        self.assertEqual(file_hash, '6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72')
        self.assertIn(' sha256 hash: 6ae8a7', ''.join(logs.output))

    def test_copy_and_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)

            src_path = temp_path / 'source.txt'
            dst_path = temp_path / 'dest.txt'

            src_path.write_bytes(b'test content')

            with self.assertLogs(level='INFO') as logs:
                file_hash = copy_and_hash(src=src_path, dst=dst_path)

            self.assertEqual(dst_path.read_bytes(), b'test content')
        self.assertEqual(file_hash, '6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72')
        self.assertIn(' backup to ', ''.join(logs.output))

    def test_read_and_hash_file(self):
        with tempfile.NamedTemporaryFile() as temp:
            temp_file_path = Path(temp.name)
            temp_file_path.write_bytes(b'test content')

            with self.assertLogs(level='INFO') as logs:
                content, file_hash = read_and_hash_file(temp_file_path)
        self.assertEqual(content, b'test content')
        self.assertEqual(file_hash, '6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72')
        self.assertIn(' sha256 hash: 6ae8a7', ''.join(logs.output))

    def test_iter_scandir_files(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)

            (temp_path / 'file1.txt').write_bytes(b'content1')
            (temp_path / 'file2.txt').write_bytes(b'content2')
            subdir = temp_path / 'subdir'
            subdir.mkdir()
            (subdir / 'file3.txt').write_bytes(b'content3')

            # Add a symlink to file1.txt
            (temp_path / 'symlink_to_file1.txt').symlink_to(temp_path / 'file1.txt')

            # Add a hardlink to file2.txt
            os.link(temp_path / 'file2.txt', temp_path / 'hardlink_to_file2.txt')

            exclude_subdir = temp_path / '__pycache__'
            exclude_subdir.mkdir()
            (exclude_subdir / 'BAM.txt').write_bytes(b'foobar')

            broken_symlink_path = temp_path / 'broken_symlink'
            broken_symlink_path.symlink_to(temp_path / 'not/existing/file.txt')

            with self.assertLogs(level='DEBUG') as logs:
                files = list(iter_scandir_files(temp_path, excludes={'__pycache__'}))

        file_names = sorted([Path(f.path).relative_to(temp_path).as_posix() for f in files])

        self.assertEqual(
            file_names,
            [
                'broken_symlink',
                'file1.txt',
                'file2.txt',
                'hardlink_to_file2.txt',
                'subdir/file3.txt',
                'symlink_to_file1.txt',
            ],
        )
        logs = ''.join(logs.output)
        self.assertIn('Scanning directory ', logs)
        self.assertIn('Excluding directory ', logs)
