import logging
from pathlib import Path


class HashAlreadyExistsError(ValueError):
    pass


class FileHashDatabase:
    """DocWrite: README.md ## FileHashDatabase
    A simple "database" to store file content hash <-> relative path mappings.
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

    def __init__(self, backup_root: Path, phlb_conf_dir: Path):
        self.backup_root = backup_root
        self.base_path = phlb_conf_dir / 'hash-lookup'
        self.base_path.mkdir(parents=False, exist_ok=True)

    def _get_hash_path(self, hash: str) -> Path:
        first_dir_name = hash[:2]
        second_dir_name = hash[2:4]
        hash_path = self.base_path / first_dir_name / second_dir_name / hash
        return hash_path

    def get(self, hash: str) -> Path | None:
        hash_path = self._get_hash_path(hash)
        try:
            rel_file_path = hash_path.read_text()
        except FileNotFoundError:
            return None
        else:
            abs_file_path = self.backup_root / rel_file_path
            if not abs_file_path.is_file():
                logging.warning('Hash database entry found, but file does not exist: %s', abs_file_path)
                hash_path.unlink()
                return None
            return abs_file_path

    def __setitem__(self, hash: str, abs_file_path: Path):
        hash_path = self._get_hash_path(hash)
        hash_path.parent.mkdir(parents=True, exist_ok=True)

        # File should be found before and results in hardlink creation!
        # So deny change of existing hashes:
        if hash_path.exists():
            raise HashAlreadyExistsError(f'Hash {hash} already exists in the database!')

        hash_path.write_text(str(abs_file_path.relative_to(self.backup_root)))
