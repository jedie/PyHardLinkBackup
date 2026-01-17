import tempfile
from pathlib import Path


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
