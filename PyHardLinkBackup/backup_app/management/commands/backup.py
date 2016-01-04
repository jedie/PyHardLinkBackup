from django.core.management.base import BaseCommand, CommandError

from PyHardLinkBackup.DjangoHardLinkBackup.models import BackupEntry

class Command(BaseCommand):
    help = "Start a Backup run"

    def add_arguments(self, parser):
        parser.add_argument('backup_name')
        parser.add_argument('filepath')

    def handle(self, *args, **options):

        BackupEntry.create()

        for poll_id in options['poll_id']:
            try:
                poll = Poll.objects.get(pk=poll_id)
            except Poll.DoesNotExist:
                raise CommandError('Poll "%s" does not exist' % poll_id)

            poll.opened = False
            poll.save()

            self.stdout.write(self.style.SUCCESS('Successfully closed poll "%s"' % poll_id))