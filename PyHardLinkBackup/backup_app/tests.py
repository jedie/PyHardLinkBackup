from unittest import mock

import os
import datetime
import hashlib

from PyHardLinkBackup.backup_app.models import BackupRun, BackupEntry
from PyHardLinkBackup.tests.base import BaseTestCase


class ModelTests(BaseTestCase):
    def test_path(self):
        test_backup_name = "Unittest"
        test_datetime = datetime.datetime(2016,1,2,hour=3,minute=4,second=5, microsecond=123456)

        test_backup_run = BackupRun.objects.create(
            name=test_backup_name,
            backup_datetime=test_datetime
        )
        test_directory=os.path.join("a","sub","dir")
        test_filename="test_filename.foo"
        test_hexdigest=hashlib.new("sha512", b"foobar").hexdigest()

        test_file_stat = mock.Mock()
        test_file_stat.st_size = 1234
        test_file_stat.st_mtime_ns = 1234567890.654321

        test_entry = BackupEntry.objects.create(
            backup_run=test_backup_run,
            directory=test_directory,
            filename=test_filename,
            hash_hexdigest=test_hexdigest,
            file_stat=test_file_stat,
        )

        self.assertEqual(
            test_entry.get_backup_path().path, # Path2() instance
            os.path.join(self.backup_path,
                "Unittest/2016-01-02-030405.123456/a/sub/dir/test_filename.foo".replace("/", os.sep)
            )
        )
