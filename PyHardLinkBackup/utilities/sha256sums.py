import logging
from pathlib import Path


logger = logging.getLogger(__name__)


def get_sha256sums_path(file_path: Path):
    """
    >>> get_sha256sums_path(Path('foo/bar/baz.txt'))
    PosixPath('foo/bar/SHA256SUMS')
    """
    hash_file_path = file_path.parent / 'SHA256SUMS'
    return hash_file_path


def store_hash(file_path: Path, file_hash: str):
    """DocWrite: README.md ## SHA256SUMS
    A `SHA256SUMS` file is stored in each backup directory containing the SHA256 hashes of all files in that directory.
    It's the same format as e.g.: `sha256sum * > SHA256SUMS` command produces.
    So it's possible to verify the integrity of the backup files later.
    e.g.:
    ```bash
    cd .../your/backup/foobar/20240101_120000/
    sha256sum -c SHA256SUMS
    ```
    """
    hash_file_path = get_sha256sums_path(file_path)
    with hash_file_path.open('a') as f:
        f.write(f'{file_hash}  {file_path.name}\n')


def check_sha256sums(
    *,
    file_path: Path,
    file_hash: str,
) -> bool | None:
    hash_file_path = get_sha256sums_path(file_path=file_path)
    if not hash_file_path.is_file():
        return None  # Nothing to verify against

    with hash_file_path.open('r') as f:
        for line in f:
            try:
                expected_hash, filename = line.split(' ', maxsplit=1)
            except ValueError:
                logger.exception(f'Invalid line in "{hash_file_path}": {line!r}')
            else:
                filename = filename.strip()
                if filename == file_path.name:
                    if not expected_hash == file_hash:
                        logger.error(
                            f'Hash {file_hash} from file {file_path} does not match hash in {hash_file_path} !'
                        )
                        return False
                    else:
                        logger.debug(f'{file_path} hash verified successfully from {hash_file_path}.')
                        return True

    logger.info('No SHA256SUMS entry found for file: %s', file_path)
    return None
