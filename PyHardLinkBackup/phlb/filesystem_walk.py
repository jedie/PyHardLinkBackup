import logging

from PyHardLinkBackup.phlb.pathlib2 import Path2, DirEntryPath, pprint_path

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
        scandir_it = Path2(top).scandir()
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
        log.error("scandir error: %s" % err)
        return

    for entry in scandir_it:
        if entry.is_dir(follow_symlinks=False):
            if deep < limit:
                yield from scandir_limited(entry.path, limit, deep)
            else:
                yield entry


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



