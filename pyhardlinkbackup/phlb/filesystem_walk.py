import collections
import logging
import sys
from pathlib import Path
from timeit import default_timer

# https://github.com/jedie/pathlib_revised/
from pathlib_revised import DirEntryPath, Path2

# https://github.com/jedie/IterFilesystem
from iterfilesystem.humanize import human_time

log = logging.getLogger(f"phlb.{__name__}")


class SkipPatternInformation:
    skip_count = 0

    def __init__(self):
        self.data = collections.defaultdict(list)

    def __call__(self, entry, pattern):
        self.skip_count += 1
        self.data[pattern].append(entry)

    def has_hits(self):
        if len(self.data) == 0:
            return False
        else:
            return True

    def short_info(self):
        if not self.data:
            return ['Nothing skipped.']
        lines = []
        for pattern, entries in sorted(self.data.items()):
            lines.append(f" * {pattern!r} match on {len(entries):d} items")
        return lines

    def long_info(self):
        if not self.data:
            return ['Nothing skipped.']
        lines = []
        for pattern, entries in sorted(self.data.items()):
            lines.append(f"{pattern!r} match on:")
            for entry in entries:
                lines.append(f" * {entry.path}")
        return lines

    def print_skip_pattern_info(self, name):
        if not self.has_hits():
            print(f"{name} doesn't match on any dir entry.")
        else:
            print(f"{name} match information:")
            for line in self.long_info():
                log.info(line)
            for line in self.short_info():
                print(f"{line}\n")


class ScanResult:
    item_count = 0
    file_count = 0
    dir_count = 0
    other_count = 0

    def __init__(self):
        self.skip_info = SkipPatternInformation()

    def __str__(self):
        return (
            f' {self.item_count} items:'
            f' {self.dir_count} directories,'
            f' {self.file_count} files,'
            f' {self.other_count} other,'
            f' {self.skip_info.skip_count} skipped'
        )


class FilesystemScanner:
    def __init__(self, top, skip_dirs=(), update_interval=0.5):
        print(f'\nScan: {top}...')
        self.top = Path(top).expanduser().resolve()
        if not self.top.is_dir():
            raise NotADirectoryError(f'Directory not exists: {self.top}')
        self.skip_dirs = skip_dirs
        self.update_interval = update_interval

        self.scan_result = ScanResult()

    def _update_callback(self, *, prefix):
        pass

    def scan(self):
        self.start_time = default_timer()
        yield from self._scan_filesystem(top=self.top, next_update=self._get_next_update())
        self.duration = default_timer() - self.start_time

    def _get_next_update(self):
        return default_timer() + self.update_interval

    def _scan_filesystem(self, top, next_update=None):
        try:
            scandir_it = Path2(top).scandir()
        except PermissionError as err:
            log.error(f"scandir error: {err}")
            return

        for entry in scandir_it:
            self.scan_result.item_count += 1
            if entry.is_dir(follow_symlinks=False):
                self.scan_result.dir_count += 1
                if entry.name in self.skip_dirs:
                    self.scan_result.skip_info(entry, entry.name)
                    continue

                # recursive scan
                yield from self._scan_filesystem(entry.path, next_update=next_update)
            elif entry.is_file(follow_symlinks=False):
                # Don't count entry.stat().st_size here, because it's very slow!
                self.scan_result.file_count += 1
            else:
                self.scan_result.other_count += 1

            yield DirEntryPath(entry)

            if default_timer() >= next_update:
                self._update_callback(prefix='scanning...')
                next_update = self._get_next_update()


class VerboseFilesystemScanner(FilesystemScanner):
    def _update_callback(self, *, prefix):
        rate = int(self.scan_result.item_count / (default_timer() - self.start_time))
        print(f'\r{prefix} {self.scan_result} (Rate: {rate} items/sec.)', end='')

    def scan(self):
        try:
            for _ in super().scan():
                continue
        except KeyboardInterrupt:
            self._update_callback(prefix=f'Scan aborted!')
            print()
            sys.exit(0)

        self._update_callback(prefix=f'Scan done in {human_time(self.duration)}:')
        print("\n\nSkip information:")
        print("\n".join(self.scan_result.skip_info.short_info()))
        print()
        return self.scan_result


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
        log.error(f"scandir error: {err}")
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
        log.error(f"scandir error: {err}")
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
        self.filter = filter

    def iter(self, dir_entries):
        """
        :param dir_entries: list of os.DirEntry() instances
        """
        filter = self.filter
        for entry in dir_entries:
            path = filter(Path2(entry.path))
            if path:
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
        try:
            dir_entry_path = DirEntryPath(entry)
        except FileNotFoundError as err:
            # e.g.: A file was deleted after the first filesystem scan
            # Will be obsolete if we use shadow-copy / snapshot function from filesystem
            # see: https://github.com/jedie/PyHardLinkBackup/issues/6
            log.error(f"Can't make DirEntryPath() instance: {err}")
            continue
        if match(dir_entry_path, match_patterns, on_skip):
            yield None
        else:
            yield dir_entry_path


if __name__ == "__main__":
    kwargs = dict(
        # top="~/",
        # top="~/backups",
        top="~/repos",
        # top="~/servershare/Backups",
        skip_dirs=(
            '__cache__', 'temp', '.git'
        ),
        update_interval=0.5
    )

    scanner = FilesystemScanner(**kwargs)
    for _ in scanner.scan():
        continue
    scan_result = scanner.scan_result
    print(f'scan done in {human_time(scanner.duration)} with: {scan_result}')

    scanner = VerboseFilesystemScanner(**kwargs)
    scanner.scan()
    scan_result = scanner.scan_result
    print(f'scan ended with: {scan_result}')

    #
    #
    #
    # from tqdm import tqdm
    #
    # # path = Path2("/")
    # # path = Path2(os.path.expanduser("~")) # .home() new in Python 3.5
    # path = Path2("../../../../").resolve()
    # print("Scan: %s..." % path)
    #
    # def on_skip(entry, pattern):
    #     log.error("Skip pattern %r hit: %s" % (pattern, entry.path))
    #
    # skip_dirs = ("__pycache__", "temp")
    #
    # tqdm_iterator = tqdm(
    #     scandir_walk(
    #         path.path,
    #         skip_dirs,
    #         on_skip=on_skip),
    #     unit=" dir entries",
    #     leave=True)
    # dir_entries = [entry for entry in tqdm_iterator]
    #
    # print()
    # print("=" * 79)
    # print("\n * %i os.DirEntry() instances" % len(dir_entries))
    #
    # match_patterns = ("*.old", ".*", "__pycache__/*", "temp", "*.pyc", "*.tmp", "*.cache")
    # tqdm_iterator = tqdm(
    #     iter_filtered_dir_entry(dir_entries, match_patterns, on_skip),
    #     total=len(dir_entries),
    #     unit=" dir entries",
    #     leave=True,
    # )
    # filtered_files = [entry for entry in tqdm_iterator if entry]
    #
    # print()
    # print("=" * 79)
    # print("\n * %i filtered Path2() instances" % len(filtered_files))
    #
    # path_iterator = enumerate(
    #     sorted(
    #         filtered_files,
    #         key=lambda x: x.stat.st_mtime,  # sort by last modify time
    #         reverse=True,  # sort from newest to oldes
    #     )
    # )
    # for no, path in path_iterator:
    #     print(no, path.stat.st_mtime, end=" ")
    #     if path.is_symlink:
    #         print("Symlink: %s" % path)
    #     elif path.is_dir:
    #         print("Normal dir: %s" % path)
    #     elif path.is_file:
    #         print("Normal file: %s" % path)
    #     else:
    #         print("XXX: %s" % path)
    #         pprint_path(path)
    #
    #     if path.different_path or path.resolve_error:
    #         print(path.pformat())
    #         print()
