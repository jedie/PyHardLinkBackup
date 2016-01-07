
from django.core.management.base import BaseCommand, CommandError

from PyHardLinkBackup.phlb.phlb_main import HardLinkBackup


class Command(BaseCommand):
    help = "Start a Backup run"

    def add_arguments(self, parser):
        parser.add_argument("path",
            help="Path to the source directory to backup"
        )

    def handle(self, *args, **options):
        src_path=options["path"]

        # FIXME for windows
        # https://www.python-forum.de/viewtopic.php?f=1&t=37786 (de)
        # e.g.:
        # called with:
        #       phlb.exe backup "%~dp0"
        # converted to:
        #       phlb.exe backup "C:\foo\bar\"
        # python will get in sys.argv this:
        #       'C:\\foo\\bar"'
        src_path = src_path.strip("\"'")

        phlb = HardLinkBackup(src_path=src_path)
        phlb.print_summary()