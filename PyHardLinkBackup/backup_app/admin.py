from django.contrib import admin

from .models import BackupFilename, BackupEntry


class BackupEntryAdmin(admin.ModelAdmin):
    list_filter = ("backup_run",)

admin.site.register(BackupEntry, BackupEntryAdmin)
admin.site.register(BackupFilename)