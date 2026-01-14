import contextlib
import logging
import unittest

from bx_py_utils.test_utils.context_managers import MassContextManager


class RaiseLogOutput(logging.Handler):
    LOGGING_FORMAT = '%(levelname)s:%(name)s:%(message)s'

    def __init__(self):
        super().__init__()
        self.setFormatter(logging.Formatter(self.LOGGING_FORMAT))

    def emit(self, record):
        raise AssertionError(
            f'Uncaptured log message during the test:\n'
            '------------------------------------------------------------------------------------\n'
            f'{self.format(record)}\n'
            '------------------------------------------------------------------------------------\n'
            '(Hint: use self.assertLogs() context manager)'
        )


class LoggingMustBeCapturedTestCaseMixin:
    def setUp(self):
        super().setUp()
        self.logger = logging.getLogger()

        self.old_handlers = self.logger.handlers[:]
        self.old_level = self.logger.level
        self.old_propagate = self.logger.propagate

        self._log_buffer_handler = RaiseLogOutput()
        self.logger.addHandler(self._log_buffer_handler)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

    def tearDown(self):
        self.logger.handlers = self.old_handlers
        self.logger.propagate = self.old_propagate
        self.logger.setLevel(self.old_level)
        super().tearDown()


class RaiseOutput(MassContextManager):
    def __init__(self, test_case: unittest.TestCase):
        self.test_case = test_case
        self.mocks = (
            contextlib.redirect_stdout(self),
            contextlib.redirect_stderr(self),
        )

    def write(self, txt):
        self.test_case.fail(
            f'Output was written during the test:\n'
            '------------------------------------------------------------------------------------\n'
            f'{txt!r}\n'
            '------------------------------------------------------------------------------------\n'
            f'(Hint: use RedirectOut context manager)'
        )

    def flush(self):
        pass

    def getvalue(self):
        return ''


class OutputMustCapturedTestCaseMixin:
    def setUp(self):
        super().setUp()
        self._cm = RaiseOutput(self)
        self._cm_result = self._cm.__enter__()

    def tearDown(self):
        self._cm.__exit__(None, None, None)
        super().tearDown()


class BaseTestCase(
    OutputMustCapturedTestCaseMixin,
    LoggingMustBeCapturedTestCaseMixin,
    unittest.TestCase,
):
    """
    A base TestCase that ensures that all logging and output is captured during tests.
    """
