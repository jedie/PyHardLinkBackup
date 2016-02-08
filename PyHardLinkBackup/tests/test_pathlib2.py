import logging
import os
import shutil
import unittest
import subprocess

log = logging.getLogger("phlb.%s" % __name__)

from PyHardLinkBackup.phlb.pathlib2 import Path2, PosixPath2, WindowsPath2, \
    DirEntryPath
from PyHardLinkBackup.tests.base import BaseTempTestCase

IS_NT = os.name == 'nt'

class TestPath2(BaseTempTestCase):
    def test_callable(self):
        self.assertTrue(callable(Path2(".").makedirs))


class TestDeepPath(BaseTempTestCase):
    def setUp(self):
        super(TestDeepPath, self).setUp()
        self.deep_path = Path2(self.temp_root_path, "A"*255, "B"*255)
        self.deep_path.makedirs()

    def tearDown(self):
        def rmtree_error(function, path, excinfo):
            log.error("\nError remove temp: %r\n%s", path, excinfo[1])
        shutil.rmtree(self.deep_path.extended_path, ignore_errors=False, onerror=rmtree_error)
        shutil.rmtree(Path2(self.temp_root_path).extended_path, ignore_errors=False, onerror=rmtree_error)
        super(BaseTempTestCase, self).tearDown()

    def test_exists(self):
        self.assertTrue(self.deep_path.is_dir())
        self.assertEqual(self.deep_path.listdir(), [])

    def test_resolve(self):
        resolved_path = self.deep_path.resolve()
        self.assertEqual(self.deep_path.path, resolved_path.path)

    def test_utime(self):
        self.deep_path.utime()
        mtime = 111111111 # UTC: 1973-07-10 00:11:51
        atime = 222222222 # UTC: 1977-01-16 01:23:42
        self.deep_path.utime(times=(atime, mtime))
        stat = self.deep_path.stat()
        self.assertEqual(stat.st_atime, atime)
        self.assertEqual(stat.st_mtime, mtime)

    def test_touch(self):
        file_path = Path2(self.deep_path, "file.txt")
        self.assertFalse(file_path.is_file())
        file_path.touch()
        self.assertTrue(file_path.is_file())

    def test_open_file(self):
        file_path = Path2(self.deep_path, "file.txt")
        with file_path.open("w") as f:
            f.write("unittests!")

        self.assertTrue(file_path.is_file())
        with file_path.open("r") as f:
            self.assertEqual(f.read(), "unittests!")

    def test_listdir(self):
        Path2(self.deep_path, "a file.txt").touch()
        self.assertEqual(self.deep_path.listdir(), ["a file.txt"])

    def test_chmod(self):
        file_path = Path2(self.deep_path, "file.txt")
        file_path.touch()
        file_path.chmod(0o777)
        if not IS_NT:
            self.assertEqual(file_path.stat().st_mode, 33279)
        file_path.chmod(0o666)
        if not IS_NT:
            self.assertEqual(file_path.stat().st_mode, 33206)

    def test_rename(self):
        old_file = Path2(self.deep_path, "old_file.txt")
        old_file.touch()

        new_file = Path2(self.deep_path, "new_file.txt")
        self.assertFalse(new_file.is_file())
        old_file.rename(new_file)
        self.assertFalse(old_file.is_file())
        self.assertTrue(new_file.is_file())

    def test_unlink(self):
        file_path = Path2(self.deep_path, "file.txt")
        file_path.touch()
        file_path.unlink()
        self.assertFalse(file_path.is_file())


@unittest.skipUnless(IS_NT, 'test requires a Windows-compatible system')
class TestWindowsPath2(unittest.TestCase):
    def test_instances(self):
        self.assertIsInstance(Path2(), WindowsPath2)
        self.assertIsInstance(Path2("."), WindowsPath2)
        self.assertIsInstance(Path2(".").resolve(), WindowsPath2)
        self.assertIsInstance(Path2.home(), WindowsPath2)

    def test_callable(self):
        self.assertTrue(callable(WindowsPath2(".").link))

    def test_extended_path_hack(self):
        abs_path = Path2("c:/foo/bar/")
        self.assertEqual(str(abs_path), "c:\\foo\\bar")
        self.assertEqual(abs_path.path, "c:\\foo\\bar")
        self.assertEqual(abs_path.extended_path, "\\\\?\\c:\\foo\\bar")

        rel_path = Path2("../foo/bar/")
        self.assertEqual(str(rel_path), "..\\foo\\bar")
        self.assertEqual(rel_path.extended_path, "..\\foo\\bar")

        with self.assertRaises(FileNotFoundError) as err:
            abs_path.resolve()
        self.assertEqual(err.exception.filename, "\\\\?\\c:\\foo\\bar")
        # self.assertEqual(err.exception.filename, "c:\\foo\\bar")

        path = Path2("~").expanduser()
        path = path.resolve()
        self.assertNotIn("\\\\?\\", str(path))

    def test_already_extended(self):
        existing_path = Path2("~").expanduser()
        extended_path = existing_path.extended_path
        self.assertTrue(extended_path.startswith("\\\\?\\"))

        # A already extended path should not added \\?\ two times:
        extended_path2 = Path2(extended_path).extended_path
        self.assertEqual(extended_path2, "\\\\?\\%s" % existing_path)
        self.assertEqual(extended_path2.count("\\\\?\\"), 1)


    def test_home(self):
        self.assertEqual(
            Path2("~/foo").expanduser().path,
            os.path.expanduser("~\\foo")
        )

        self.assertEqual(
            Path2("~/foo").expanduser().extended_path,
            "\\\\?\\%s" % os.path.expanduser("~\\foo")
        )

        existing_path = Path2("~").expanduser()
        ref_path = os.path.expanduser("~")
        self.assertEqual(str(existing_path), "%s" % ref_path)
        self.assertEqual(existing_path.extended_path, "\\\\?\\%s" % ref_path)
        self.assertTrue(existing_path.is_dir())
        self.assertTrue(existing_path.exists())

        self.assertEqual(str(existing_path), str(existing_path.resolve()))

    def test_relative_to(self):
        path1 = Path2("C:\\foo")
        path2 = Path2("C:\\foo\\bar")
        self.assertEqual(path2.relative_to(path1).path, "bar")

        path1 = Path2("\\\\?\\C:\\foo")
        path2 = Path2("\\\\?\\C:\\foo\\bar")
        self.assertEqual(path2.relative_to(path1).path, "bar")

        path1 = Path2("C:\\foo")
        path2 = Path2("\\\\?\\C:\\foo\\bar")
        self.assertEqual(path2.relative_to(path1).path, "bar")

        path1 = Path2("\\\\?\\C:\\foo")
        path2 = Path2("C:\\foo\\bar")
        self.assertEqual(path2.relative_to(path1).path, "bar")


@unittest.skipIf(IS_NT, 'test requires a POSIX-compatible system')
class TestPosixPath2(unittest.TestCase):

    def test_instances(self):
        self.assertIsInstance(Path2(), PosixPath2)
        self.assertIsInstance(Path2("."), PosixPath2)
        self.assertIsInstance(Path2.home(), PosixPath2)
        self.assertIsInstance(Path2.home().resolve(), PosixPath2)

    def test_callable(self):
        self.assertTrue(callable(PosixPath2(".").utime))

    def test_extended_path(self):
        # extended_path exists just for same API
        self.assertEqual(PosixPath2("foo/bar").path, "foo/bar")
        self.assertEqual(PosixPath2("foo/bar").extended_path, "foo/bar")

    def test_home(self):
        self.assertEqual(
            str(Path2("~").expanduser()),
            os.path.expanduser("~")
        )
        self.assertEqual(
            Path2("~/foo").expanduser().path,
            os.path.expanduser("~/foo")
        )


class TestDirEntryPath(BaseTempTestCase):
    """
    Test DirEntryPath() on all platforms
    """
    def test_normal_file(self):
        f = Path2("normal_file.txt")
        f.touch()
        self.assertTrue(f.is_file())

        p = Path2(self.temp_root_path)
        dir_entries = tuple(p.scandir())
        print(dir_entries)
        self.assertEqual(len(dir_entries), 1)

        dir_entry = dir_entries[0]

        dir_entry_path = DirEntryPath(dir_entry)
        print(dir_entry_path.pformat())

        self.assertEqual(dir_entry_path.is_symlink, False)
        self.assertEqual(dir_entry_path.different_path, False)
        self.assertEqual(
            dir_entry_path.resolved_path,
            Path2(Path2(p, f).extended_path)
        )
        self.assertEqual(dir_entry_path.resolve_error, None)


@unittest.skipIf(os.name != 'nt', 'test requires a Windows-compatible system')
class TestDirEntryPathWindows(BaseTempTestCase):

    # TODO: Make similar tests under Linux, too!

    def subprocess_run(self, *args, timeout=1, returncode=0, **kwargs):
        default_kwargs = {"shell": True}
        default_kwargs.update(kwargs)
        p = subprocess.Popen(args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **kwargs
        )
        stderr_bytes = p.communicate(timeout=timeout)[0]

        # The following will not work:
        # encoding = sys.stdout.encoding or locale.getpreferredencoding()
        # In PyCharm:
        #   sys.stdout.encoding = None
        #   locale.getpreferredencoding() = "cp1252"
        # In SciTE:
        #   sys.stdout.encoding = "cp1252"
        #   locale.getpreferredencoding() = "cp1252"
        # under cmd.exe:
        #   sys.stdout.encoding = "cp850"
        txt = stderr_bytes.decode("cp850")
        self.assertEqual(p.returncode, returncode,
            msg = (
                "Command '%s' return code wrong!\n"
                " *** command output: ***\n"
                "%s"
            ) % (" ".join(args), txt)
        )
        return txt

    def test_subprocess_encoding(self):
        txt = self.subprocess_run("cmd.exe", "/c", 'echo "abcäöüß"')
        print(txt)
        self.assertIn("abcäöüß", txt)

    def mklink(self, *args, returncode=0):
        return self.subprocess_run(
            "cmd.exe", "/c", "mklink", *args,
            returncode=returncode
        )

    def test_mklink(self):
        txt = self.mklink("/?",
            returncode=1 # Why in hell is the return code for the help page ==1 ?!?
        )
        print(txt)
        self.assertIn("MKLINK [[/D] | [/H] | [/J]]", txt)

    def test_directory_junction(self):
        os.mkdir("dir1")
        dir1 = Path2("dir1").resolve()
        dir2 = Path2(self.temp_root_path, "dir2")
        print(dir1.path)
        print(dir2.path)

        # mklink /d /j <destination> <source>
        # Strange that first is destination and second is the source path !
        txt = self.mklink("/d", "/j", "dir2", "dir1")
        print(txt)
        self.assertIn("dir2 <<===>> dir1", txt)

        p = Path2(self.temp_root_path)
        dir_entries = list(p.scandir())
        dir_entries.sort(key=lambda x: x.name)
        print(dir_entries)
        self.assertEqual(repr(dir_entries), "[<DirEntry 'dir1'>, <DirEntry 'dir2'>]")

        dir_entry1, dir_entry2 = dir_entries
        self.assertEqual(dir_entry1.name, "dir1")
        self.assertEqual(dir_entry2.name, "dir2")

        dir_entry_path1 = DirEntryPath(dir_entry1)
        print(dir_entry_path1.pformat())
        self.assertEqual(dir_entry_path1.is_symlink, False)
        self.assertEqual(dir_entry_path1.different_path, False)
        self.assertEqual(
            dir_entry_path1.resolved_path,
            Path2(Path2(self.temp_root_path, "dir1").extended_path)
        )
        self.assertEqual(dir_entry_path1.resolve_error, None)

        dir_entry_path2 = DirEntryPath(dir_entry2)
        print(dir_entry_path2.pformat())
        self.assertEqual(dir_entry_path2.is_symlink, False)
        self.assertEqual(dir_entry_path2.different_path, True) # <<--- because of junction
        self.assertEqual( # pointed to dir1 !
            dir_entry_path2.resolved_path,
            Path2(Path2(self.temp_root_path, "dir1").extended_path)
        )
        self.assertEqual(dir_entry_path2.resolve_error, None)

        # remove junction source and try again
        # dir1.unlink() # Will not work: PermissionError: [WinError 5] Zugriff verweigert
        dir1.rename("new_name") # Will also break the junction ;)

        # check again:
        dir_entry_path2 = DirEntryPath(
            dir_entry2,
            onerror=print # will be called, because resolve can't be done.
        )
        print(dir_entry_path2.pformat())
        self.assertEqual(dir_entry_path2.is_symlink, False)
        self.assertEqual(dir_entry_path2.different_path, True) # <<--- because of junction

        # can't be resole, because source was renamed:
        self.assertEqual(dir_entry_path2.resolved_path, None)
        self.assertIsInstance(dir_entry_path2.resolve_error, FileNotFoundError)

