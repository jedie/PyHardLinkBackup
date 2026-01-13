from unittest import TestCase

from bx_py_utils.doc_write.api import GeneratedInfo, generate
from bx_py_utils.path import assert_is_file

from PyHardLinkBackup.cli_dev import PACKAGE_ROOT


class DocuWriteApiTestCase(TestCase):
    def test_up2date_docs(self):
        """DocWrite: about-docs.md # generate Doc-Write

        These documentation files are generated automatically with the "Doc-Write" tool.
        They updated automatically by unittests.

        More information about Doc-Write can be found here:

        https://github.com/boxine/bx_py_utils/tree/master/bx_py_utils/doc_write
        """
        assert_is_file(PACKAGE_ROOT / 'pyproject.toml')

        info: GeneratedInfo = generate(base_path=PACKAGE_ROOT)
        self.assertGreaterEqual(len(info.paths), 1)
        self.assertEqual(info.update_count, 0, 'No files should be updated, commit the changes')
        self.assertEqual(info.remove_count, 0, 'No files should be removed, commit the changes')
