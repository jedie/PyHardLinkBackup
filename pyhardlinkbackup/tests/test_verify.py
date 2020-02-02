import hashlib

# https://github.com/jedie/pathlib_revised/
from pathlib_revised import Path2

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.backup_app.models import ContentInfo
from pyhardlinkbackup.phlb.config import phlb_config
from pyhardlinkbackup.tests.base import BaseCreatedOneBackupsTestCase


class TestTwoBackups(BaseCreatedOneBackupsTestCase):
    def test_verify_all_ok(self):
        result = self.invoke_cli("verify", self.first_run_path)
        print(result.output)
        self.assertIn("5 File entry exist in database.", result.output)
        self.assertIn("Verify done.", result.output)
        self.assertNotIn("ERROR", result.output)

    def test_file_not_found(self):
        file_path = Path2(self.first_run_path, "sub dir A", "dir_A_file_B.txt")
        file_path.unlink()

        result = self.invoke_cli("verify", self.first_run_path)
        print(result.output)
        self.assertIn("5 File entry exist in database.", result.output)
        self.assertIn("ERROR", result.output)
        self.assertIn("Verify done.", result.output)
        self.assertIn(f"File not found: {file_path.path}", result.output)

    def test_hash_file_not_found(self):
        file_path = Path2(self.first_run_path, "sub dir A", f"dir_A_file_B.txt.{phlb_config.hash_name}")
        file_path.unlink()

        result = self.invoke_cli("verify", self.first_run_path)
        print(result.output)
        self.assertIn("5 File entry exist in database.", result.output)
        self.assertIn("ERROR", result.output)
        self.assertIn("Verify done.", result.output)
        self.assertIn(f"Hash file not found: {file_path.path}", result.output)

    def test_hash_file_mismatch(self):
        file_path = Path2(self.first_run_path, "sub dir A", f"dir_A_file_B.txt.{phlb_config.hash_name}")
        with file_path.open("w") as f:
            hash = hashlib.new(phlb_config.hash_name)
            hash.update(b"wrong content")
            f.write(hash.hexdigest())

        result = self.invoke_cli("verify", self.first_run_path)
        print(result.output)
        self.assertIn("5 File entry exist in database.", result.output)
        self.assertIn("ERROR", result.output)
        self.assertIn("Verify done.", result.output)

        self.assertIn("Hash file mismatch:", result.output)

    def test_content_mismatch(self):
        file_path = Path2(self.first_run_path, "sub dir A", "dir_A_file_B.txt")
        with file_path.open("wb") as f:
            f.write(b"wrong content")

        result = self.invoke_cli("verify", self.first_run_path)
        print(result.output)
        self.assertIn("5 File entry exist in database.", result.output)
        self.assertIn("ERROR", result.output)
        self.assertIn("Verify done.", result.output)

        self.assertIn("File content changed:", result.output)

    def test_size_changed(self):
        content_info = ContentInfo.objects.get(pk=3)
        content_info.file_size = 999
        content_info.save()

        result = self.invoke_cli("verify", self.first_run_path, "--fast")
        print(result.output)
        self.assertIn("5 File entry exist in database.", result.output)
        self.assertIn("ERROR", result.output)
        self.assertIn("Verify done.", result.output)

        self.assertIn("File size mismatch: 20 != 999", result.output)
