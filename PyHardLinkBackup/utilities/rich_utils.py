from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table
from rich.text import Text

from PyHardLinkBackup.utilities.humanize import human_filesize


class HumanFileSizeColumn(ProgressColumn):
    def __init__(self, field_name: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.field_name = field_name

    def render(self, task):
        if self.field_name is None:
            file_size = task.completed
        else:
            try:
                file_size = task.fields[self.field_name]
            except KeyError:
                raise KeyError(f'Field {self.field_name=} not found in: {task.fields.keys()=}') from None
        return Text(f'| {human_filesize(file_size)}')


class BackupProgress:
    def __init__(self, src_file_count: int, src_total_size: int):
        self.overall_progress = Progress(
            TaskProgressColumn(),
            BarColumn(bar_width=50),
            TextColumn('Elapsed:'),
            TimeElapsedColumn(),
            TextColumn('Remaining:'),
            TimeRemainingColumn(),
        )
        self.overall_progress_task_id = self.overall_progress.add_task(description='', total=100)

        self.file_count_progress = Progress(
            TaskProgressColumn(),
            BarColumn(bar_width=50),
            TextColumn('{task.completed} Files'),
        )
        self.file_count_progress_task_id = self.file_count_progress.add_task(description='', total=src_file_count)
        self.file_count_progress_task = self.file_count_progress.tasks[0]

        self.file_size_progress = Progress(
            TaskProgressColumn(),
            BarColumn(bar_width=50),
            HumanFileSizeColumn(),
            '|',
            TransferSpeedColumn(),
        )
        self.file_size_progress_task_id = self.file_size_progress.add_task(description='', total=src_total_size)
        self.file_size_progress_task = self.file_size_progress.tasks[0]

        progress_table = Table.grid()
        progress_table.add_row(Panel(self.overall_progress, title='[b]Overall Backup Progress', border_style='green'))
        progress_table.add_row(Panel(self.file_count_progress, title='Total files saved'))
        progress_table.add_row(Panel(self.file_size_progress, title='Total file size processed'))

        self.live = Live(progress_table, auto_refresh=False)

    def __enter__(self):
        self.live.__enter__()
        return self

    def update(self, backup_count: int, backup_size: int):
        self.file_count_progress.update(
            task_id=self.file_count_progress_task_id,
            completed=backup_count,
            refresh=True,
        )
        self.file_size_progress.update(
            task_id=self.file_size_progress_task_id,
            completed=backup_size,
            refresh=True,
        )
        self.overall_progress.update(
            task_id=self.overall_progress_task_id,
            completed=(self.file_count_progress_task.percentage + self.file_size_progress_task.percentage) / 2,
            refresh=True,
        )
        self.live.refresh()

    def __exit__(self, exc_type, exc_value, traceback):
        self.overall_progress.stop()
        self.file_count_progress.stop()
        self.file_size_progress.stop()
        self.live.__exit__(exc_type, exc_value, traceback)
