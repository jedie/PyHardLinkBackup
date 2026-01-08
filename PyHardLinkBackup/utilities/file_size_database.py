from pathlib import Path


class FileSizeDatabase:
    """
    A simple database to track which file sizes have been seen.
    Uses a directory structure to avoid too many files in a single directory.

    Path structure:
         {base_dst}/.phlb/size-lookup/{XX}/{YY}/{size}
    e.g.:
        1234567890 results in: {base_dst}/.phlb/size-lookup/12/34/1234567890

    Notes:
      * no padding is made, so the min size is 1000 bytes!
      * We don't "cache" anything in Memory, to avoid high memory consumption for large datasets.
    """

    def __init__(self, backup_root: Path):
        self.base_path = backup_root / '.phlb' / 'size-lookup'
        self.base_path.mkdir(parents=False, exist_ok=True)

    def _get_size_path(self, size: int) -> Path:
        assert size >= 1000, 'Size must be at least 1000 bytes'
        size_str = str(size)
        first_dir_name = size_str[:2]
        second_dir_name = size_str[2:4]
        size_path = self.base_path / first_dir_name / second_dir_name / size_str
        return size_path

    def __contains__(self, size: int) -> bool:
        size_path = self._get_size_path(size)
        return size_path.exists()

    def add(self, size: int):
        size_path = self._get_size_path(size)
        if not size_path.exists():
            size_path.parent.mkdir(parents=True, exist_ok=True)
            size_path.touch(exist_ok=False)
