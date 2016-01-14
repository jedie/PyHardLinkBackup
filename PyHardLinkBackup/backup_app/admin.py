from django.contrib import admin

from .models import BackupRun, BackupFilename, BackupEntry, ContentInfo


class BackupEntryAdmin(admin.ModelAdmin):
    list_filter = ("backup_run","no_link_source")

admin.site.register(BackupEntry, BackupEntryAdmin)
admin.site.register(BackupRun)
admin.site.register(BackupFilename)
admin.site.register(ContentInfo)
