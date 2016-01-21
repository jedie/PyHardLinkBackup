"""
    Windows specific tests
"""
import logging
import os
import pprint
import shutil
import unittest

import sys

import pathlib

from PyHardLinkBackup.backup_app.models import BackupEntry
from PyHardLinkBackup.tests.base import BaseSourceDirTestCase
from PyHardLinkBackup.tests.utils import UnittestFileSystemHelper


@unittest.skipUnless(sys.platform.startswith("win"), "Test only for Windows")
class WindowsTestCase(BaseSourceDirTestCase):

    @unittest.skipIf("FAST_TEST" in os.environ, "Skip slow test")
    def test_link_limit(self):
        """
        NTFS filesystem has a limit of 1024 hard links on a file.
        see: https://msdn.microsoft.com/en-us/library/aa363860%28v=vs.85%29.aspx

        We test this in two backup runs:
            1. Backup 1022 files with same content (-> 1022 hardlinks)
            2. Backup another 4 files (A,B,C,D) with the same content

        The 2nd backup run can create another hardlink
        the the files "A" and "B"...
        Try to hardlink "C" will result in the cascade to find
        a useable file from the newest ot oldest file:

            Can't link 'BAK2/foo A.ext' to 'BAK2/foo C.ext'
            Can't link 'BAK2/foo B.ext' to 'BAK2/foo C.ext'
            Can't link 'BAK1/file 0001.txt' to 'BAK2/foo C.ext'
            ...
            Can't link 'BAK1/file 1020.txt' to 'BAK2/foo C.ext'
            Can't link 'BAK1/file 1021.txt' to 'BAK2/foo C.ext'
            Can't link 'BAK1/file 1022.txt' to 'BAK2/foo C.ext'

        ("BAK1": path of the first backup run and "BAK2" the 2nd run)

        In the end, all 1024 files are marked as "no_link_source" and
        the file "C" will be stored as a normal file and will be used
        for the next file "D" as a hardlink source.
        """

        print("\nCreate files with the same content")
        compare_list = []
        for no in range(1, 1023):
            # for no in range(1, 10):
            p = pathlib.Path(self.source_path, "file %04i.txt" % no)
            # p.write_text('unittest!') # new in Python 3.5
            with p.open("w") as f:
                f.write("unittest!")

            compare_list.append('file %04i.txt                  L - unittest!' % no)
            compare_list.append('file %04i.txt.sha512           F - e3770...f651c' % no)

        print("Backup all files")
        result = self.invoke_cli("backup", self.source_path)
        # print(result.output)

        self.assertIn("9.0 KB in 1022 files to backup.", result.output)
        self.assertIn("new content to saved: 1 files (9 Bytes 0.1%)", result.output)
        self.assertIn("stint space via hardlinks: 1021 files (9.0 KB 99.9%)", result.output)

        self.assertEqual(BackupEntry.objects.all().count(), 1022)
        self.assertEqual(BackupEntry.objects.filter(no_link_source=True).count(), 0)
        self.assertEqual(BackupEntry.objects.filter(no_link_source=False).count(), 1022)

        first_run_path = self.get_newest_backup_path()

        log_content = self.get_log_content(pathlib.Path(first_run_path + ".log"))
        self.assertIn("Replaced with a hardlink", log_content)
        self.assertNotIn("ERROR", log_content)

        compare_list.insert(0, first_run_path)
        # print("\n".join(compare_list))

        fs_helper = UnittestFileSystemHelper()
        # fs_helper.print_tree(self.backup_path)

        tree_list = fs_helper.pformat_tree(first_run_path, with_timestamps=False)
        # pprint.pprint(tree_list,indent=0, width=200)

        self.assertListEqual(tree_list, compare_list)

        # Delete all old test files:
        shutil.rmtree(self.source_path)
        os.mkdir(self.source_path)

        # Create another files with the same empty "content"
        for i in ("A", "B", "C", "D"):
            p = pathlib.Path(self.source_path, "foo %s.ext" % i)
            with p.open("w") as f:
                f.write("unittest!")

        # Backup only the other files
        with self.assertLogs(logging.getLogger("phlb"), level=logging.ERROR) as cm:
            result = self.invoke_cli("backup", self.source_path)
            print(result.output)

            second_run_path = self.get_newest_backup_path()

            # print("first_run_path:", first_run_path)
            # print("second_run_path:", second_run_path)

            logs = cm.output[:3] + cm.output[-3:]
            # pprint.pprint(logs, indent=0, width=200)
            logs = [
                entry.replace(first_run_path, "BAK1").replace(second_run_path, "BAK2")\
                .replace("\\","/").split(":")[2]
                for entry in logs
            ]
            logs.insert(3, "...")
            # pprint.pprint(logs, indent=0, width=200)

            self.assertListEqual(logs, [
                "Can't link 'BAK2/foo A.ext' to 'BAK2/foo C.ext'",
                "Can't link 'BAK2/foo B.ext' to 'BAK2/foo C.ext'",
                "Can't link 'BAK1/file 0001.txt' to 'BAK2/foo C.ext'",
                '...',
                "Can't link 'BAK1/file 1020.txt' to 'BAK2/foo C.ext'",
                "Can't link 'BAK1/file 1021.txt' to 'BAK2/foo C.ext'",
                "Can't link 'BAK1/file 1022.txt' to 'BAK2/foo C.ext'"
            ])

        self.assertIn("36 Bytes in 4 files to backup.", result.output)
        self.assertIn("new content to saved: 1 files (9 Bytes 25.0%)", result.output)
        self.assertIn("stint space via hardlinks: 3 files (27 Bytes 75.0%)", result.output)

        tree_list = fs_helper.pformat_tree(second_run_path, with_timestamps=False)
        # pprint.pprint(tree_list, indent=0, width=200)
        self.assertListEqual(tree_list, [
            second_run_path,
            'foo A.ext                      L - unittest!',
            'foo A.ext.sha512               F - e3770...f651c',
            'foo B.ext                      L - unittest!',
            'foo B.ext.sha512               F - e3770...f651c',
            'foo C.ext                      L - unittest!',
            'foo C.ext.sha512               F - e3770...f651c',
            'foo D.ext                      L - unittest!',
            'foo D.ext.sha512               F - e3770...f651c'
        ])

        self.assertEqual(BackupEntry.objects.all().count(), 1026)
        self.assertEqual(BackupEntry.objects.filter(no_link_source=True).count(), 1024)
        self.assertEqual(BackupEntry.objects.filter(no_link_source=False).count(), 2)

        entries = list(BackupEntry.objects.filter(no_link_source=False)\
            .values_list("filename__filename", flat=True))
        # pprint.pprint(entries, indent=0, width=200)
        self.assertEqual(entries, ['foo C.ext', 'foo D.ext'])
