import re
import sys
from contextlib import redirect_stdout


# Borrowed from click:
_ansi_re = re.compile(r'\033\[[;?0-9]*[a-zA-Z]')


def strip_ansi_codes(value: str) -> str:
    return _ansi_re.sub('', value)


class TeeStdout:
    def __init__(self, file):
        self.file = file
        self.stdout = sys.stdout

    def write(self, data):
        self.stdout.write(data)
        self.file.write(strip_ansi_codes(data))

    def flush(self):
        self.stdout.flush()
        self.file.flush()


class TeeStdoutContext:
    def __init__(self, file_path):
        self.file_path = file_path

    def __enter__(self):
        self.file = open(self.file_path, 'w')
        self.redirect = redirect_stdout(TeeStdout(self.file))
        self.redirect.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.redirect.__exit__(exc_type, exc_val, exc_tb)
        self.file.close()
