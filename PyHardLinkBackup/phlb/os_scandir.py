import fnmatch
import logging
import os

# Use the built-in version of scandir/walk if possible, otherwise
# use the scandir module version
try:
    from os import scandir # new in Python 3.5
except ImportError:
    # use https://pypi.python.org/pypi/scandir
    try:
        from scandir import scandir
    except ImportError:
        raise ImportError("For Python <2.5: Please install 'scandir' !")

log = logging.getLogger("phlb.%s" % __name__)

def fnmatches(filename, patterns):
    for pattern in patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True
    return False


def walk2(top, skip_dirs, skip_files, followlinks=False):
    """
    Same as os.walk() except:
     - returns os.scandir() result (os.DirEntry() instance) and not entry.name
     - always topdown=True
    """
    dirs = []
    nondirs = []

    # We may not have read permission for top, in which case we can't
    # get a list of the files the directory contains.  os.walk
    # always suppressed the exception then, rather than blow up for a
    # minor reason when (say) a thousand readable directories are still
    # left to visit.  That logic is copied here.
    try:
        scandir_it = scandir(top)
    except OSError:
        return

    while True:
        try:
            try:
                entry = next(scandir_it)
            except StopIteration:
                break
        except OSError:
            return

        try:
            is_dir = entry.is_dir()
        except OSError:
            # If is_dir() raises an OSError, consider that the entry is not
            # a directory, same behaviour than os.path.isdir().
            is_dir = False

        if is_dir:
            if entry.name not in skip_dirs:
                dirs.append(entry)
            else:
                log.debug("Skip directory: %r", entry.name)
        else:
            if not fnmatches(entry.name, skip_files):
                nondirs.append(entry)
            else:
                log.debug("Skip file: %r", entry.name)

    yield top, dirs, nondirs

    # Recurse into sub-directories
    islink = os.path.islink
    for entry in dirs:
        # Issue #23605: os.path.islink() is used instead of caching
        # entry.is_symlink() result during the loop on os.scandir() because
        # the caller can replace the directory entry during the "yield"
        # above.
        if followlinks or not islink(entry.path):
            yield from walk2(entry.path, skip_dirs, skip_files, followlinks)