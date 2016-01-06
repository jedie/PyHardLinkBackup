from django.contrib import admin

from .models import Config, BackupRun, BackupFilename, BackupEntry, ContentInfo


class BackupEntryAdmin(admin.ModelAdmin):
    list_filter = ("backup_run",)

admin.site.register(Config)

admin.site.register(BackupEntry, BackupEntryAdmin)
admin.site.register(BackupRun)
admin.site.register(BackupFilename)
admin.site.register(ContentInfo)
