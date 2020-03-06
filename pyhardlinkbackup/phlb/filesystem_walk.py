import logging

# https://github.com/jedie/pathlib_revised/
from pathlib_revised import Path2

log = logging.getLogger(__name__)


def scandir_limited(top, limit, deep=0):
    """
    yields only directories with the given deep limit

    :param top: source path
    :param limit: how deep should be scanned?
    :param deep: internal deep number
    :return: yields os.DirEntry() instances
    """
    deep += 1
    try:
        scandir_it = Path2(top).scandir()
    except PermissionError as err:
        log.error(f"scandir error: {err}")
        return

    for entry in scandir_it:
        if entry.is_dir(follow_symlinks=False):
            if deep < limit:
                yield from scandir_limited(entry.path, limit, deep)
            else:
                yield entry
