from django.contrib import admin

from .models import BackupEntry, BackupFilename, BackupRun, ContentInfo


class BackupEntryAdmin(admin.ModelAdmin):
    def backup_name(self, obj):
        return obj.backup_run.name

    backup_name.short_description = "Backup Name"

    def path(self, obj):
        return obj.get_backup_path()

    path.short_description = "Path"

    list_display = ("backup_name", "no_link_source", "path")
    list_filter = ("no_link_source",)


admin.site.register(BackupEntry, BackupEntryAdmin)


class BackupRunAdmin(admin.ModelAdmin):
    list_display = ("name", "completed", "backup_datetime", "path_part")
    date_hierarchy = "backup_datetime"
    list_filter = ("name", "completed")


admin.site.register(BackupRun, BackupRunAdmin)


admin.site.register(BackupFilename)
admin.site.register(ContentInfo)
