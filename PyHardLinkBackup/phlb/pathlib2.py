import logging
import os
import pathlib
import shutil


# Use the built-in version of scandir/walk if possible, otherwise
# use the scandir module version
import functools

try:
    from os import scandir # new in Python 3.5
except ImportError:
    # use https://pypi.python.org/pypi/scandir
    try:
        from scandir import scandir
    except ImportError:
        raise ImportError("For Python <2.5: Please install 'scandir' !")


log = logging.getLogger("phlb.%s" % __name__)

IS_WINDOWS = os.name == 'nt'


class SharedPathMethods:
    def copyfile(self, other, *args, **kwargs):
        shutil.copyfile(self.extended_path, other.extended_path, *args, **kwargs)

    def expanduser(self):
        return Path2(os.path.expanduser(self.extended_path))

    def link(self, other):
        os.link(self.extended_path, other.extended_path)

    def listdir(self):
        return os.listdir(self.extended_path)

    def makedirs(self, *args, **kwargs):
        os.makedirs(self.extended_path, *args, **kwargs)

    @property
    def path(self):
        # Path2().path is new in 3.4.5 and 3.5.2
        return str(self)

    def utime(self, *args, **kwargs):
        """ Set the access and modified times of the file specified by path. """
        os.utime(self.extended_path, *args, **kwargs)

    def scandir(self):
        return scandir(self.extended_path)


class WindowsPath2(SharedPathMethods, pathlib.WindowsPath):
    def stat(self):
        return os.stat(self.extended_path)

    def open(self, *args):
        return open(self.extended_path, *args)

    def _raw_open(self, flags, mode=0o777):
        if self._closed:
            self._raise_closed()
        return os.open(self.extended_path, flags, mode)

    def chmod(self, *args):
        return os.chmod(self.extended_path, *args)

    def unlink(self):
        return os.unlink(self.extended_path)

    def rename(self, target):
        return os.rename(self.extended_path, Path2(target).extended_path)

    def resolve(self):
        path = super(WindowsPath2, self)._flavour.resolve(self.extended_path)
        return Path2(path)

    @classmethod
    def _from_parts(cls, args, init=True):
        """
        Strip \\?\ prefix in init phase
        """
        if args:
            args = list(args)
            if isinstance(args[0], WindowsPath2):
                args[0] = args[0].path
            elif args[0].startswith("\\\\?\\"):
                args[0] = args[0][4:]
            args = tuple(args)
        return super(WindowsPath2, cls)._from_parts(args, init)

    @property
    def extended_path(self):
        """
        Add prefix \\?\ to every absolute path, so that it's a "extended-length"
        path, that should be longer than 259 characters (called: "MAX_PATH")
        see:
        https://msdn.microsoft.com/en-us/library/aa365247.aspx#maxpath
        """
        if self.is_absolute() and not self.path.startswith("\\\\"):
            return "\\\\?\\%s" % self.path
        return self.path

    @property
    def path(self):
        """
        Return the path always without the \\?\ prefix.
        """
        path = super(WindowsPath2, self).path
        if path.startswith("\\\\?\\"):
            return path[4:]
        return path

    def relative_to(self, other):
        """
        Important here is, that both are always the same:
        both with \\?\ prefix or both without it.
        """
        return super(WindowsPath2, Path2(self.path)).relative_to(Path2(other).path)


class PosixPath2(SharedPathMethods, pathlib.PosixPath):
    @property
    def extended_path(self):
        return self.path


class Path2(pathlib.Path):
    """
    https://github.com/python/cpython/blob/master/Lib/pathlib.py
    """
    def __new__(cls, *args, **kwargs):
        if cls is Path2 or cls is pathlib.Path:
            cls = WindowsPath2 if IS_WINDOWS else PosixPath2
        self = cls._from_parts(args, init=False)
        if not self._flavour.is_supported:
            raise NotImplementedError("cannot instantiate %r on your system"
                                      % (cls.__name__,))
        self._init()
        return self

    @classmethod
    def home(cls):
        """
        Return a new path pointing to the user's home directory (as
        returned by os.path.expanduser('~'))
        """
        # Note: pathlib.Path.home() exist since in Python 3.5
        return cls(os.path.expanduser("~"))


class DirEntryPath:
    """
    A Path2() instance from a os.DirEntry() instance that
    holds some more cached information.

    e.g.:

    * junction under windows:
        self.is_symlink = False
        self.different_path = True
        self.resolved_path = Path2() instance from junction destination

    * broken junction under windows:
        self.is_symlink = False
        self.different_path = True
        self.resolved_path = None
        self.resolve_error: contains the Error instance

    * symlink under linux:
        self.is_symlink = True
        self.different_path = True
        self.resolved_path = Path2() instance from symlink destination
        self.resolve_error = None

    * broken symlink under linux:
        self.is_symlink = True
        self.different_path = True
        self.resolved_path = None
        self.resolve_error: contains the Error instance
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
            self.different_path = self.path_instance.path != self.resolved_path.path

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


def pprint_path(path):
    """
    print information of a pathlib / os.DirEntry() instance with all "is_*" functions.
    """
    print("\n*** %s" % path)
    for attrname in sorted(dir(path)):
        if attrname.startswith("is_"):
            value = getattr(path, attrname)
            print("%20s: %s" % (attrname, value))
    print()
