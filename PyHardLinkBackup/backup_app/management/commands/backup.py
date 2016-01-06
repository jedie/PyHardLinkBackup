
import sys

if not hasattr(sys, "real_prefix"):
    print("ERROR: virtualenv not activated!")
    sys.exit("-1")

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
        phlb = HardLinkBackup(src_path=src_path)
        phlb.print_summary()