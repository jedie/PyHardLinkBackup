from click._compat import strip_ansi

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.phlb.traceback_plus import exc_plus


class SummaryFileHelper:
    def __init__(self, summary_file):
        self.summary_file = summary_file

    def __call__(self, *parts, sep=" ", end="\n", flush=False, verbose=True):
        if verbose:
            print(*parts, sep=sep, end=end, flush=flush)

        self.summary_file.write(sep.join([strip_ansi(str(i)) for i in parts]))
        self.summary_file.write(end)
        if flush:
            self.summary_file.flush()

    def handle_low_level_error(self):
        self("_" * 79)
        self("ERROR: Backup aborted with a unexpected error:")

        for line in exc_plus():
            self(line)

        self("-" * 79)
        self("Please report this Bug here:")
        self("https://github.com/jedie/PyHardLinkBackup/issues/new", flush=True)
        self("-" * 79)
