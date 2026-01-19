import time

from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    Task,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.style import Style
from rich.table import Table
from rich.text import Text

from PyHardLinkBackup.constants import LAGE_FILE_PROGRESS_MIN_SIZE
from PyHardLinkBackup.utilities.humanize import human_filesize


class HumanFileSizeColumn(ProgressColumn):
    def __init__(self, field_name: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.field_name = field_name

    def render(self, task):
        if self.field_name is None:
            advance_size = task.completed
            remaining_size = task.remaining
            return (
                Text('Achieved: ', style='white')
                + Text(
                    human_filesize(advance_size),
                    style='progress.elapsed',
                )
                + Text(' Remaining: ', style='white')
                + Text(
                    human_filesize(remaining_size),
                    style='progress.remaining',
                )
            )

        else:
            try:
                advance_size = task.fields[self.field_name]
            except KeyError:
                raise KeyError(f'Field {self.field_name=} not found in: {task.fields.keys()=}') from None
        return Text(human_filesize(advance_size))


class TransferSpeedColumn2(ProgressColumn):
    def __init__(self, *args, unit: str = 'it', **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.unit = unit

    def render(self, task: Task) -> Text:
        speed = task.finished_speed or task.speed
        if speed is None:
            return Text('?', style='grey50')
        if speed < 0.1:
            return Text('-', style='grey50')
        return Text(f'{speed:.1f} {self.unit}/s', style='progress.data.speed')


class DisplayFileTreeProgress:
    def __init__(self, *, description: str, total_file_count: int, total_size: int):
        percent_kwargs = dict(
            text_format='[progress.percentage]{task.percentage:>3.1f}%',
            justify='right',
        )
        self.overall_progress_bar = Progress(TaskProgressColumn(**percent_kwargs), BarColumn(bar_width=None))
        self.file_count_progress_bar = Progress(TaskProgressColumn(**percent_kwargs), BarColumn(bar_width=None))
        self.file_size_progress_bar = Progress(TaskProgressColumn(**percent_kwargs), BarColumn(bar_width=None))

        self.overall_progress = Progress(
            TextColumn('Elapsed:'),
            TimeElapsedColumn(),
            TextColumn('Remaining:'),
            TimeRemainingColumn(),
        )
        self.file_count_progress = Progress(
            TextColumn(
                '[white]Achieved: [progress.elapsed]{task.completed}[white]'
                ' Remaining: [progress.remaining]{task.remaining}'
            ),
            '|',
            TransferSpeedColumn2(unit='files'),
        )
        self.file_size_progress = Progress(
            HumanFileSizeColumn(),
            '|',
            TransferSpeedColumn(),
        )

        self.overall_progress_task_bar = self.overall_progress_bar.add_task('', total=100)
        self.file_count_progress_task_bar = self.file_count_progress_bar.add_task('', total=total_file_count)
        self.file_size_progress_task_bar = self.file_size_progress_bar.add_task('', total=total_size)

        self.overall_progress_task_time = self.overall_progress.add_task('', total=100)
        self.file_count_progress_task_time = self.file_count_progress.add_task('', total=total_file_count)
        self.file_size_progress_task_time = self.file_size_progress.add_task('', total=total_size)

        progress_table = Table(box=None, expand=True, padding=(0, 2), show_header=False)
        progress_table.add_row('[b]Overall Progress', self.overall_progress_bar, self.overall_progress)
        progress_table.add_row('Total files saved', self.file_count_progress_bar, self.file_count_progress)
        progress_table.add_row('Total file size processed', self.file_size_progress_bar, self.file_size_progress)

        self.file_count_progress_task = self.file_count_progress.tasks[0]
        self.file_size_progress_task = self.file_size_progress.tasks[0]

        self.live = Live(
            Panel(
                progress_table,
                title=Text(description, style='progress.data.speed'),
                border_style=Style(color='blue', bold=True),
            ),
            auto_refresh=False,
        )

    def __enter__(self):
        self.live.__enter__()
        return self

    def update(
        self,
        completed_file_count: int | None = None,
        advance_size: int | None = None,
        completed_size: int | None = None,
    ):
        if completed_file_count is not None:
            self.file_count_progress_bar.update(self.file_count_progress_task_bar, completed=completed_file_count)
            self.file_count_progress.update(self.file_count_progress_task_time, completed=completed_file_count)

        if completed_size is not None:
            self.file_size_progress_bar.update(self.file_size_progress_task_bar, completed=completed_size)
            self.file_size_progress.update(self.file_size_progress_task_time, completed=completed_size)
        elif advance_size is not None:
            self.file_size_progress_bar.update(self.file_size_progress_task_bar, advance=advance_size)
            self.file_size_progress.update(self.file_size_progress_task_time, advance=advance_size)

        overall_completed = (self.file_count_progress_task.percentage + self.file_size_progress_task.percentage) / 2

        self.overall_progress_bar.update(self.overall_progress_task_bar, completed=overall_completed)
        self.overall_progress.update(self.overall_progress_task_time, completed=overall_completed)

        self.live.refresh()

    def __exit__(self, exc_type, exc_value, traceback):
        self.overall_progress.stop()
        self.file_count_progress.stop()
        self.file_size_progress.stop()
        self.live.__exit__(exc_type, exc_value, traceback)


class NoopProgress(DisplayFileTreeProgress):
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def update(self, *args, **kwargs):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        return bool(exc_type)


class LargeFileProgress:
    def __init__(self, description: str, *, parent_progress: DisplayFileTreeProgress, total_size: int):
        self.description = description
        self.parent_progress = parent_progress
        self.total_size = total_size

        self.progress = None

    def __enter__(self):
        is_large_file = self.total_size > LAGE_FILE_PROGRESS_MIN_SIZE
        if is_large_file:
            self.start_time = time.monotonic()
            self.next_update = self.start_time + 1
            self.advance = 0
        else:
            # No progress indicator for small files
            self.next_update = None
        return self

    def update(self, advance: int):
        if not self.next_update:
            # Small file -> no progress indicator
            return

        self.advance += advance

        now = time.monotonic()
        if now <= self.next_update:
            return
        self.next_update = now + 1

        if not self.progress:
            percent_done = self.advance / self.total_size
            if percent_done >= 0.4:
                # After 1 sec. is 40 % done, we are probably done soon!
                # Avoid showing progress bar for fast operations
                self.next_update = None  # No progress indicator
                return

            self.progress = Progress(
                TaskProgressColumn(text_format='[progress.percentage]{task.percentage:>3.1f}%'),
                BarColumn(bar_width=None, finished_style=Style(color='rgb(0,100,0)')),
                HumanFileSizeColumn(),
                '|',
                TransferSpeedColumn(),
                '|',
                TextColumn('Elapsed:'),
                TimeElapsedColumn(),
                TextColumn('Remaining:'),
                TimeRemainingColumn(),
            )
            self.progress.log(f'Large file processing start: {self.description}')
            self.task_id = self.progress.add_task(
                description=self.description,
                total=self.total_size,
                start_time=self.start_time,
            )
            self.live = Live(
                Panel(self.progress, title=self.description, border_style=Style(color='yellow', bold=True)),
                auto_refresh=False,
            )
            self.live.__enter__()

        self.parent_progress.update(advance_size=self.advance)
        self.progress.update(task_id=self.task_id, advance=self.advance, refresh=True)
        self.live.refresh()
        self.advance = 0

    def __exit__(self, exc_type, exc_value, traceback):
        if self.progress:
            self.progress.log(f'Large file processing finished: {self.description}')
            self.progress.update(task_id=self.task_id, advance=self.advance, refresh=True)
            self.progress.stop()
            self.live.renderable.border_style = 'grey50'
            self.live.refresh()
            self.live.__exit__(exc_type, exc_value, traceback)
            print('\n')  # Add spacing after progress bar
