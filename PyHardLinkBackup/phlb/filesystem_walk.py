
import logging

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

from PyHardLinkBackup.phlb.pathlib2 import Path2


log = logging.getLogger("phlb.%s" % __name__)


def scandir_walk(top, skip_dirs=(), on_skip=None):
    """
    Just walk the filesystem tree top-down with os.scandir() and don't follow symlinks.
    :param top: path to scan
    :param skip_dirs: List of dir names to skip
        e.g.: "__pycache__", "temp", "tmp"
    :param on_skip: function that will be called if 'skip_dirs' match.
        e.g.:
        def on_skip(entry, pattern):
            log.error("Skip pattern %r hit: %s" % (pattern, entry.path))
    :return: yields os.DirEntry() instances
    """
    # We may not have read permission for top, in which case we can't
    # get a list of the files the directory contains.  os.walk
    # always suppressed the exception then, rather than blow up for a
    # minor reason when (say) a thousand readable directories are still
    # left to visit.  That logic is copied here.
    try:
        scandir_it = scandir(top)
    except PermissionError as err:
        log.error("scandir error: %s" % err)
        return

    for entry in scandir_it:
        if entry.is_dir(follow_symlinks=False):
            if entry.name in skip_dirs:
                on_skip(entry, entry.name)
            else:
                yield from scandir_walk(entry.path, skip_dirs, on_skip)
        else:
            yield entry


def pprint_path(path):
    """
    print information of a pathlib / os.DirEntry() instance with all "is_*" functions.
    """
    print("\n*** %s" % path)
    for attrname in sorted(dir(path)):
        if attrname.startswith("is_"):
            print("%20s: %s" % (attrname, getattr(path, attrname)()))
    print()


class PathLibFilter:
    def __init__(self, filter):
        """
        :param filter: callable to filter in self.iter()
        """
        assert callable(filter)
        self.filter=filter

    def iter(self, dir_entries):
        """
        :param dir_entries: list of os.DirEntry() instances
        """
        filter = self.filter
        for entry in dir_entries:
            path = filter(Path2(entry.path))
            if path != False:
                yield path


class DirEntryPath:
    """
    A Path2() instance from a os.DirEntry() instance that
    holds some more cached informations.

    e.g.:

    * junction under windows:
        self.is_symlink = False
        self.different_path = True
        self.resolved_path = Path2() instance from junction destination

    * symlink under linux:
        self.is_symlink = True
        self.different_path = True
        self.resolved_path = Path2() instance from symlink destination
        self.resolve_error = None

    * broken symlink under linux:
        self.is_symlink = True
        self.different_path = True
        self.resolved_path = None
        self.resolve_error contains the Error instance
    """
    def __init__(self, dir_entry, onerror=log.error):
        """
        :param dir_entry: os.DirEntry() instance
        """
        self.dir_entry = dir_entry
        self.path = dir_entry.path

        self.is_symlink = dir_entry.is_symlink()
        self.is_file = dir_entry.is_file(follow_symlinks=False)
        self.is_dir = dir_entry.is_dir(follow_symlinks=False)
        self.stat = dir_entry.stat(follow_symlinks=False)

        self.path_instance = Path2(self.path)
        try:
            self.resolved_path = self.path_instance.resolve()
        except (PermissionError, FileNotFoundError) as err:
            onerror("Resolve %r error: %s" % (self.path, err))
            self.resolved_path = None
            self.resolve_error = err
        else:
            self.resolve_error = None

        if self.resolved_path is None:
            # e.g.: broken symlink under linux
            self.different_path = True
        else:
            # e.g.: a junction under windows
            # https://www.python-forum.de/viewtopic.php?f=1&t=37725&p=290429#p290428 (de)
            self.different_path = self.path != self.resolved_path.path

    def pformat(self):
        return "\n".join((
            " *** %s :" % self,
            "path.......: %r" % self.path,
            "path instance..: %r" % self.path_instance,
            "resolved path..: %r" % self.resolved_path,
            "resolve error..: %r" % self.resolve_error,
            "different path.: %r" % self.different_path,
            "is symlink.....: %r" % self.is_symlink,
            "is file........: %r" % self.is_file,
            "is dir.........: %r" % self.is_dir,
            "stat.size......: %r" % self.stat.st_size,
        ))

    def __str__(self):
        return "<DirEntryPath %s>" % self.path_instance


def iter_filtered_dir_entry(dir_entries, match_patterns, on_skip):
    """
    Filter a list of DirEntryPath instances with the given pattern

    :param dir_entries: list of DirEntryPath instances
    :param match_patterns: used with Path.match()
        e.g.: "__pycache__/*", "*.tmp", "*.cache"
    :param on_skip: function that will be called if 'match_patterns' hits.
        e.g.:
        def on_skip(entry, pattern):
            log.error("Skip pattern %r hit: %s" % (pattern, entry.path))
    :return: yields None or DirEntryPath instances
    """
    def match(dir_entry_path, match_patterns, on_skip):
        for match_pattern in match_patterns:
            if dir_entry_path.path_instance.match(match_pattern):
                on_skip(dir_entry_path, match_pattern)
                return True
        return False

    for entry in dir_entries:
        dir_entry_path = DirEntryPath(entry)
        if match(dir_entry_path, match_patterns, on_skip):
            yield None
        else:
            yield dir_entry_path



if __name__ == '__main__':
    from tqdm import tqdm

    # path = Path2("/")
    # path = Path2(os.path.expanduser("~")) # .home() new in Python 3.5
    path = Path2("../../../../").resolve()
    print("Scan: %s..." % path)

    def on_skip(entry, pattern):
        log.error("Skip pattern %r hit: %s" % (pattern, entry.path))

    skip_dirs=("__pycache__", "temp")

    tqdm_iterator = tqdm(
        scandir_walk(path.path, skip_dirs, on_skip=on_skip),
        unit=" dir entries",
        leave=True
    )
    dir_entries = [entry for entry in tqdm_iterator]

    print()
    print("="*79)
    print("\n * %i os.DirEntry() instances" % len(dir_entries))

    match_patterns=(
        "*.old", ".*",
        "__pycache__/*", "temp",
        "*.pyc", "*.tmp", "*.cache",
    )
    tqdm_iterator = tqdm(
        iter_filtered_dir_entry(dir_entries, match_patterns, on_skip),
        total=len(dir_entries),
        unit=" dir entries",
        leave=True
    )
    filtered_files = [entry for entry in tqdm_iterator if entry]

    print()
    print("="*79)
    print("\n * %i filtered Path2() instances" % len(filtered_files))

    path_iterator = enumerate(sorted(
        filtered_files,
        key=lambda x: x.stat.st_mtime, # sort by last modify time
        reverse=True # sort from newest to oldes
    ))
    for no, path in path_iterator:
        print(no, path.stat.st_mtime, end=" ")
        if path.is_symlink:
            print("Symlink: %s" % path)
        elif path.is_dir:
            print("Normal dir: %s" % path)
        elif path.is_file:
            print("Normal file: %s" % path)
        else:
            print("XXX: %s" % path)
            pprint_path(path)

        if path.different_path or path.resolve_error:
            print(path.pformat())
            print()



