import os
import pathlib
import shutil


class SharedPathMethods:
    @property
    def path(self):
        # Path2().path is new in 3.4.5 and 3.5.2
        return str(self)

    def makedirs(self, *args, **kwargs):
        os.makedirs(self.path, *args, **kwargs)

    def link(self, other):
        os.link(self.path, other.path)

    def utime(self, *args, **kwargs):
        os.utime(self.path, *args, **kwargs)

    def copyfile(self, other, *args, **kwargs):
        shutil.copyfile(self.path, other.path, *args, **kwargs)

    def expanduser(self):
        return Path2(os.path.expanduser(self.path))


class WindowsPath2(SharedPathMethods, pathlib.WindowsPath):
    pass


class PosixPath2(SharedPathMethods, pathlib.PosixPath):
    pass


class Path2(pathlib.Path):
    """
    https://github.com/python/cpython/blob/master/Lib/pathlib.py
    """
    def __new__(cls, *args, **kwargs):
        if cls is Path2 or cls is pathlib.Path:
            cls = WindowsPath2 if os.name == 'nt' else PosixPath2
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
        try:
            return pathlib.Path.home()
        except AttributeError:
            # Exist since in Python 3.5
            return cls(os.path.expanduser("~"))



def test():
    assert PosixPath2("foo/bar").path == "foo/bar"

    assert Path2.home().path == os.path.expanduser("~")
    assert Path2("~/foo").expanduser().path == os.path.expanduser("~/foo")

    assert callable(Path2(".").makedirs)
    if os.name == 'nt':
        assert callable(WindowsPath2(".").link)
    else:
        assert callable(PosixPath2(".").utime)


if __name__ == '__main__':
    test()
