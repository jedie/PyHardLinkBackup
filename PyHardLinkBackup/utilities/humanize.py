import time

from bx_py_utils.humanize.time import human_timedelta


def human_filesize(size: int | float) -> str:
    """
    >>> human_filesize(1024)
    '1.00 KiB'
    >>> human_filesize(2.2*1024)
    '2.20 KiB'
    >>> human_filesize(3.33*1024*1024)
    '3.33 MiB'
    >>> human_filesize(4.44*1024*1024*1024)
    '4.44 GiB'
    >>> human_filesize(5.55*1024*1024*1024*1024)
    '5.55 TiB'
    >>> human_filesize(6.66*1024*1024*1024*1024*1024)
    '6.66 PiB'
    """
    for unit in ['Bytes', 'KiB', 'MiB', 'GiB', 'TiB']:
        if size < 1024.0:
            return f'{size:.2f} {unit}'
        size /= 1024.0
    return f'{size:.2f} PiB'


class PrintTimingContextManager:
    def __init__(self, description: str):
        self.description = description

    def __enter__(self) -> None:
        self.start_time = time.perf_counter()

    def __exit__(self, exc_type, exc_value, traceback):
        duration = time.perf_counter() - self.start_time
        print(f'{self.description}: {human_timedelta(duration)}')
        if exc_type:
            return False  # Do not suppress exceptions
