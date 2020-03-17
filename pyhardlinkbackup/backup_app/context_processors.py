# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup import __version__


def phlb_version_string(request):
    return {
        "version_string": f"v{__version__}"
    }
