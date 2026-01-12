import collections
import hashlib
import logging
import time
from pathlib import Path

from bx_py_utils.path import assert_is_dir
from cli_base.cli_tools.verbosity import setup_logging
from cli_base.tyro_commands import TyroVerbosityArgType
from rich import print  # noqa

from PyHardLinkBackup.cli_app import app
from PyHardLinkBackup.utilities.filesystem import iter_scandir_files


logger = logging.getLogger(__name__)


@app.command
def benchmark_hashes(
    base_path: Path,
    /,
    max_duration: int = 30,  # in seconds
    min_file_size: int = 15 * 1024,  # 15 KiB
    max_file_size: int = 100 * 1024 * 1024,  # 100 MiB
    verbosity: TyroVerbosityArgType = 1,
) -> None:
    """
    Benchmark different file hashing algorithms on the given path

    Example output:

    Total files hashed: 220, total size: 1187.7 MiB

    Results:
    Total file content read time: 1.7817s

    sha1       | Total: 0.6827s | 0.4x hash/read
    sha256     | Total: 0.7189s | 0.4x hash/read
    sha224     | Total: 0.7375s | 0.4x hash/read
    sha384     | Total: 1.6552s | 0.9x hash/read
    blake2b    | Total: 1.6708s | 0.9x hash/read
    md5        | Total: 1.6870s | 0.9x hash/read
    sha512     | Total: 1.7269s | 1.0x hash/read
    shake_128  | Total: 1.9834s | 1.1x hash/read
    sha3_224   | Total: 2.3006s | 1.3x hash/read
    sha3_256   | Total: 2.3856s | 1.3x hash/read
    shake_256  | Total: 2.4375s | 1.4x hash/read
    blake2s    | Total: 2.5219s | 1.4x hash/read
    sha3_384   | Total: 3.2596s | 1.8x hash/read
    sha3_512   | Total: 4.5328s | 2.5x hash/read
    """
    setup_logging(verbosity=verbosity)
    assert_is_dir(base_path)
    print(f'Benchmarking file hashes under: {base_path}')

    print(f'Min file size: {min_file_size} bytes')
    print(f'Max file size: {max_file_size} bytes')
    print(f'Max duration: {max_duration} seconds')

    algorithms = sorted(hashlib.algorithms_guaranteed)
    print(f'\nUsing {len(algorithms)} guaranteed algorithms: {algorithms}')
    print('-' * 80)

    file_count = 0
    total_size = 0
    total_read_time = 0.0
    results = collections.defaultdict(set)

    start_time = time.time()
    stop_time = start_time + max_duration
    next_update = start_time + 2

    for dir_entry in iter_scandir_files(base_path):
        entry_stat = dir_entry.stat()
        file_size = entry_stat.st_size
        if not (min_file_size <= file_size <= max_file_size):
            continue

        start_time = time.perf_counter()
        file_content = Path(dir_entry.path).read_bytes()
        duration = time.perf_counter() - start_time
        total_read_time += duration

        for algo in algorithms:
            # Actual measurement:
            start_time = time.perf_counter()
            hashlib.new(algo, file_content)
            duration = time.perf_counter() - start_time

            results[algo].add(duration)

        file_count += 1
        total_size += entry_stat.st_size

        now = time.time()
        if now >= stop_time:
            print('Reached max duration limit, stopping benchmark...')
            break

        if now >= next_update:
            percent = (now - (stop_time - max_duration)) / max_duration * 100
            print(
                f'{int(percent)}% Processed {file_count} files so far,'
                f' total size: {total_size / 1024 / 1024:.1f} MiB...'
            )
            next_update = now + 2

    print(f'\nTotal files hashed: {file_count}, total size: {total_size / 1024 / 1024:.1f} MiB')

    print('\nResults:')
    print(f'Total file content read time: {total_read_time:.4f}s\n')

    sorted_results = sorted(
        ((algo, sum(durations)) for algo, durations in results.items()),
        key=lambda x: x[1],  # Sort by total_duration
    )
    for algo, total_duration in sorted_results:
        ratio = total_duration / total_read_time
        print(f'{algo:10} | Total: {total_duration:.4f}s | {ratio:.1f}x hash/read')
