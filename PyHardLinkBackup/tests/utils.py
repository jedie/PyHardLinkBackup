import datetime
import subprocess

import os
import posixpath
import sys


class UnittestFileSystemHelper(object):
    DATETIME_FORMATTER="%Y%m%d:%H%M%S"

    def set_test_stat(self, path):
        atime = 222222222 # 1977-01-16 01:23:42
        mtime = 111111111 # 1973-07-10 01:11:51
        os.utime(path, (atime, mtime))

    def create_test_fs(self, fs_dict, dir=None):
        for name, data in fs_dict.items():
            path = os.path.normpath(os.path.join(dir, name))
            if isinstance(data, dict):
                os.mkdir(path)
                self.create_test_fs(data, dir=path)
            else:
                with open(path, "w") as f:
                    f.write(data)

            self.set_test_stat(path)

    def pformat_tree(self, path, with_timestamps):

        def pformat_stat(path):
            result = ["%-30s" % posixpath.normpath(path)]
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
                mtime = stat.st_mtime
                dt = datetime.datetime.fromtimestamp(mtime)
                mtime_string = dt.strftime(self.DATETIME_FORMATTER)
                result.append(mtime_string)

            return " ".join(result)

        cwd = os.getcwd()
        os.chdir(path)

        lines = []
        for root, dirs, files in os.walk("."):
            if root == ".":
                lines.append(posixpath.normpath(os.path.abspath(root)))
            else:
                lines.append(pformat_stat(root))

            for file_name in sorted(files):
                file_path = os.path.join(root, file_name)
                with open(file_path, "r") as f:
                    content = f.read()

                if len(content) > 30:
                    content = "%s...%s" % (content[:5], content[-5:])

                lines.append("%s - %s" % (pformat_stat(file_path), content))

        lines.sort()
        os.chdir(cwd)
        return lines

    def print_tree(self, path):
        if sys.platform.startswith("linux"):
            # http://mama.indstate.edu/users/ice/tree/
            try:
                subprocess.Popen(["tree", "--inodes", path]).wait()
            except FileNotFoundError as err:
                raise FileNotFoundError(
                    "Please install the linux package 'tree' - Origin Error: %s" % err
                )
        else:
            raise NotImplementedError("TODO: %s" % sys.platform)