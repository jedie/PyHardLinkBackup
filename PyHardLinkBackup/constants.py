from pathlib import Path

import PyHardLinkBackup


CLI_EPILOG = 'Project Homepage: https://github.com/jedie/PyHardLinkBackup'

BASE_PATH = Path(PyHardLinkBackup.__file__).parent


##########################################################################
# "Settings" for PyHardLinkBackup:

HASH_ALGO = 'sha256'
SMALL_FILE_THRESHOLD = 1000  # bytes
CHUNK_SIZE = 64 * 1024 * 1024  # 64 MB
LAGE_FILE_PROGRESS_MIN_SIZE = CHUNK_SIZE * 3

