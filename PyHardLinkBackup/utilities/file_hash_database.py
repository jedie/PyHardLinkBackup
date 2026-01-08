from pathlib import Path


class HashAlreadyExistsError(ValueError):
    pass


class FileHashDatabase:
    """
    A simple database to store file content hash <-> relative path mappings.
    Uses a directory structure to avoid too many files in a single directory.
    Path structure:
            {base_dst}/.phlb/hash-lookup/{XX}/{YY}/{hash}
    e.g.:
        hash '12ab000a1b2c3...' results in: {base_dst}/.phlb/hash-lookup/12/ab/12ab000a1b2c3...

    Notes:
      * Hash length will be not validated, so it can be used with any hash algorithm.
      * The "relative path" that will be stored is not validated, so it can be any string.
      * We don't "cache" anything in Memory, to avoid high memory consumption for large datasets.
    """
    def __init__(self, backup_root: Path):
        self.base_path = backup_root / '.phlb' / 'hash-lookup'
        self.base_path.mkdir(parents=False, exist_ok=True)

    def _get_hash_path(self, hash: str) -> Path:
        first_dir_name = hash[:2]
        second_dir_name = hash[2:4]
        hash_path = self.base_path / first_dir_name / second_dir_name / hash
        return hash_path

    def get(self, hash: str) -> str | None:
        hash_path = self._get_hash_path(hash)
        try:
            return hash_path.read_text()
        except FileNotFoundError:
            return None

    def __setitem__(self, hash: str, relative_path: str):
        hash_path = self._get_hash_path(hash)
        hash_path.parent.mkdir(parents=True, exist_ok=True)

        # File should be found before and results in hardlink creation!
        # So deny change of existing hashes:
        if hash_path.exists():
            raise HashAlreadyExistsError(f'Hash {hash} already exists in the database!')

        hash_path.write_text(relative_path)
