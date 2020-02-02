from django.core.management.base import BaseCommand

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.phlb.add import add_all_backups


class Command(BaseCommand):
    help = 'Scan all existing backup and add missing ones to database.'

    def handle(self, *args, **options):
        self.stdout.write(f'\n\n{self.help}\n')
        add_all_backups()
        self.stdout.write(self.style.SUCCESS('done'))
