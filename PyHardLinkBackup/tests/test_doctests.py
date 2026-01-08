from bx_py_utils.test_utils.unittest_utils import BaseDocTests

import PyHardLinkBackup


class DocTests(BaseDocTests):
    def test_doctests(self):
        self.run_doctests(
            modules=(PyHardLinkBackup,),
        )
