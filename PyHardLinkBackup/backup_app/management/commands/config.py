
from django.core.management.base import BaseCommand
from PyHardLinkBackup.phlb.config import phlb_config

class Command(BaseCommand):
    help = "Create/edit .ini config file"

    def handle(self, *args, **options):
        # open existing .ini file
        phlb_config.open_editor()
