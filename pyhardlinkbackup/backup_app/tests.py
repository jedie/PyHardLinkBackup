import datetime
import os

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.backup_app.models import BackupRun
from pyhardlinkbackup.tests.base import BaseTestCase


class ModelTests(BaseTestCase):
    def test_path(self):
        test_backup_name = "Unittest"
        test_datetime = datetime.datetime(
            2016, 1, 2, hour=3, minute=4, second=5, microsecond=123456
        )

        test_backup_run = BackupRun(name=test_backup_name, backup_datetime=test_datetime)
        backup_path = test_backup_run.path_part()
        os.makedirs(backup_path.path)  # created so that...
        test_backup_run.save()  # ...phlb_config.ini can be created

        # Check if we get the BackupRun instance by path via phlb_config.ini
        test_backup_run2 = BackupRun.objects.get_from_config_file(backup_path)
        self.assertEqual(test_backup_run.pk, test_backup_run2.pk)
