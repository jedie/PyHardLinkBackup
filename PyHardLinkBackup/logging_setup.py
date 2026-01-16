import logging
import sys
from pathlib import Path
from typing import Annotated, Literal

import tyro
from bx_py_utils.path import assert_is_dir
from rich import (
    get_console,
    print,  # noqa
)
from rich.logging import RichHandler


logger = logging.getLogger(__name__)

LogLevelLiteral = Literal['debug', 'info', 'warning', 'error']


TyroConsoleLogLevelArgType = Annotated[
    LogLevelLiteral,
    tyro.conf.arg(
        help='Log level for console logging.',
    ),
]
DEFAULT_CONSOLE_LOG_LEVEL: TyroConsoleLogLevelArgType = 'warning'


TyroLogFileLevelArgType = Annotated[
    LogLevelLiteral,
    tyro.conf.arg(
        help='Log level for the log file',
    ),
]
DEFAULT_LOG_FILE_LEVEL: TyroLogFileLevelArgType = 'info'


def log_level_name2int(level_name: str) -> int:
    level_name = level_name.upper()
    level_mapping = logging.getLevelNamesMapping()
    try:
        return level_mapping[level_name]
    except KeyError as err:
        raise ValueError(f'Invalid log level name: {level_name}') from err


console = get_console()


class LoggingManager:
    def __init__(
        self,
        *,
        console_level: TyroConsoleLogLevelArgType,
        file_level: TyroLogFileLevelArgType,
    ):
        self.console_level_name = console_level
        self.console_level: int = log_level_name2int(console_level)
        self.file_level_name = file_level
        self.file_level: int = log_level_name2int(file_level)

        self.lowest_level = min(self.console_level, self.file_level)

        if console_level == logging.DEBUG:
            log_format = '(%(name)s) %(message)s'
        else:
            log_format = '%(message)s'

        console.print(
            f'(Set [bold]console[bold] log level: [cyan]{self.console_level_name}[/cyan])',
            justify='right',
        )
        handler = RichHandler(console=console, omit_repeated_times=False)
        handler.setLevel(self.console_level)
        logging.basicConfig(
            level=self.lowest_level,
            format=log_format,
            datefmt='[%x %X.%f]',
            handlers=[handler],
            force=True,
        )
        sys.excepthook = self.log_unhandled_exception

    def start_file_logging(self, log_file: Path):
        console.print(
            f'(initialize log file [bold]{log_file}[/bold] with level: [cyan]{self.file_level_name}[/cyan])',
            justify='right',
        )

        assert_is_dir(log_file.parent)

        root_logger = logging.getLogger()

        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(self.file_level)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        file_handler.setFormatter(formatter)

        root_logger.addHandler(file_handler)

    def log_unhandled_exception(self, exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            logger.info('Program interrupted by user (KeyboardInterrupt). Exiting...')
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
        else:
            logger.exception(
                'Unhandled exception occurred:',
                exc_info=(exc_type, exc_value, exc_traceback),
            )


class NoopLoggingManager(LoggingManager):
    """
    Only for tests: A logging manager that does nothing.
    """
    def __init__(self, *args, **kwargs):
        pass

    def start_file_logging(self, log_file: Path):
        pass
