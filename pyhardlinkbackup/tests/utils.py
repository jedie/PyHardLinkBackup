import datetime
import os
import posixpath
import subprocess
import sys


def force_posixpath(path):
    return posixpath.normpath(path.replace(os.sep, "/"))


class UnittestFileSystemHelper:
    """
    Creates test files in filesystem.
    Every test file has his own mtime. So that the order
    is always the same.
    """

    DATETIME_FORMATTER = "%Y%m%d:%H%M%S"

    def __init__(self):
        self.mtime_offset = 0
        self.default_mtime = 111111111  # UTC: 1973-07-10 00:11:51
        self.default_mtime_string = "19730710:001151"

        mtime_string = self.timestamp2string(self.default_mtime)
        assert mtime_string == self.default_mtime_string, f"{mtime_string} != {self.default_mtime_string}"

    def timestamp2string(self, timestamp):
        dt = datetime.datetime.utcfromtimestamp(timestamp)
        return dt.strftime(self.DATETIME_FORMATTER)

    def set_test_stat(self, path):
        atime = 222222222  # UTC: 1977-01-16 01:23:42
        os.utime(path, (atime, self.default_mtime + self.mtime_offset))

        # check mtime:
        if self.mtime_offset == 0:
            mtime_string = self.timestamp2string(os.stat(path).st_mtime)
            assert mtime_string == self.default_mtime_string, f"{mtime_string} != {self.default_mtime_string}"

    def create_test_fs(self, fs_dict, dir=None):
        for name, data in sorted(fs_dict.items()):
            path = os.path.normpath(os.path.join(dir, name))
            if isinstance(data, dict):
                os.mkdir(path)
                self.create_test_fs(data, dir=path)
            else:
                with open(path, "w") as f:
                    f.write(data)

            self.set_test_stat(path)
            self.mtime_offset += 1

    def pformat_tree(self, path, with_timestamps):
        def pformat_stat(path):
            result = ["%-30s" % force_posixpath(path)]
            stat = os.stat(path)

            if os.path.isfile(path):
                # Note: os.path.islink(path) check only 'symlink' and not 'hardlink' !
                if stat.st_nlink > 1:
                    fs_type = "L"
                else:
                    fs_type = "F"
            elif os.path.isdir(path):
                fs_type = "D"
            else:
                fs_type = "?"

            result.append(fs_type)

            if with_timestamps:
                result.append(self.timestamp2string(stat.st_mtime))

            return " ".join(result)

        cwd = os.getcwd()
        os.chdir(path)

        lines = []
        for root, dirs, files in os.walk("."):
            if root == ".":
                lines.append(os.path.abspath(root))
            else:
                lines.append(pformat_stat(root))

            for file_name in sorted(files):
                file_path = os.path.join(root, file_name)
                with open(file_path, "r") as f:
                    content = f.read()

                if len(content) > 30:
                    content = f"{content[:5]}...{content[-5:]}"

                lines.append(f"{pformat_stat(file_path)} - {content}")

        lines.sort()
        os.chdir(cwd)
        return lines

    def print_tree(self, path):
        if sys.platform.startswith("linux"):
            # http://mama.indstate.edu/users/ice/tree/
            args = ["tree", "--inodes", path]
            kwargs = {}
        elif sys.platform.startswith("win"):
            args = ["tree", path, "/f", "/a"]
            kwargs = {"shell": True}  # otherwise: File Not Found
        else:
            raise NotImplementedError(f"TODO: {sys.platform}")

        subprocess.run(args, timeout=5, check=True, **kwargs)


class PatchOpen:
    """
    used for patch file open routine, e.g.:

    with mock.patch('io.open', PatchOpen(open, deny_paths)) as p:
        io.open("foo", "r")
        assert_pformat_equal(p.raise_count, 0)
    """

    def __init__(self, origin_open, deny_paths):
        self.origin_open = origin_open
        self.deny_paths = deny_paths
        self.call_count = 0
        self.raise_count = 0

    def __call__(self, filepath, mode, *args, **kwargs):
        self.call_count += 1
        assert isinstance(filepath, str), repr(filepath)
        if filepath in self.deny_paths:
            self.raise_count += 1
            raise OSError("unittests raise")

        return self.origin_open(filepath, mode, *args, **kwargs)
