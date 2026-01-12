from pathlib import Path

import PyHardLinkBackup


CLI_EPILOG = 'Project Homepage: https://github.com/jedie/PyHardLinkBackup'

BASE_PATH = Path(PyHardLinkBackup.__file__).parent


##########################################################################
# "Settings" for PyHardLinkBackup:

CHUNK_SIZE = 64 * 1024 * 1024  # 64 MB
SMALL_FILE_THRESHOLD = 1000  # bytes
HASH_ALGO = 'sha256'
