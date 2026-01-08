from pathlib import Path

import PyHardLinkBackup


CLI_EPILOG = 'Project Homepage: https://github.com/jedie/PyHardLinkBackup'

BASE_PATH = Path(PyHardLinkBackup.__file__).parent


##########################################################################
# "Settings" for PyHardLinkBackup:

CHUNK_SIZE = 65536  # bytes
SMALL_FILE_THRESHOLD = 4096  # bytes
HASH_ALGO = 'sha256'
