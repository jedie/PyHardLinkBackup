import pathlib
import tempfile
from pathlib import Path
from unittest.mock import patch

from bx_py_utils.test_utils.context_managers import MassContextManager


class TemporaryDirectoryPath(tempfile.TemporaryDirectory):
    """
    Similar to tempfile.TemporaryDirectory,
    but returns a resolved Path instance.
    """

    def __enter__(self) -> Path:
        super().__enter__()
        return Path(self.name).resolve()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return super().__exit__(exc_type, exc_val, exc_tb)


class CollectOpenFiles(MassContextManager):
    def __init__(self, root: Path):
        self.root = root

        self.origin_open = open
        self.mocks = (
            patch('builtins.open', self.open_mock),
            patch.object(pathlib.Path, 'open', self.make_path_open_wrapper()),
        )
        self.opened_for_read = []
        self.opened_for_write = []

    def open_mock(self, file, mode='r', *args, **kwargs):
        rel_path = Path(file).resolve().relative_to(self.root)

        if 'r' in mode and '+' not in mode:
            if file in self.opened_for_read:
                raise RuntimeError(f'File {rel_path} already opened for read')
            self.opened_for_read.append(f'{mode} {rel_path}')
        elif any(m in mode for m in 'wax+'):
            if file in self.opened_for_write:
                raise RuntimeError(f'File {rel_path} already opened for write')
            self.opened_for_write.append(f'{mode} {rel_path}')
        else:
            raise RuntimeError(f'Unsupported file open {mode=}')

        return self.origin_open(file, mode, *args, **kwargs)

    def make_path_open_wrapper(self):
        def open_wrapper(path_self, *args, **kwargs):
            return self.open_mock(path_self, *args, **kwargs)

        return open_wrapper
