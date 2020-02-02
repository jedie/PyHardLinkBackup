import logging

# https://github.com/jedie/pathlib_revised/
from pathlib_revised import Path2

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.backup_app.models import BackupEntry
from pyhardlinkbackup.phlb.config import phlb_config
from pyhardlinkbackup.phlb.path_helper import rename2temp

log = logging.getLogger(f"phlb.{__name__}")


def deduplicate(backup_entry, hash_hexdigest):
    abs_dst_root = Path2(phlb_config.backup_path)

    try:
        backup_entry.relative_to(abs_dst_root)
    except ValueError as err:
        raise ValueError(f"Backup entry not in backup root path: {err}")

    assert backup_entry.is_file(), f"Is not a file: {backup_entry.path}"

    old_backups = BackupEntry.objects.filter(content_info__hash_hexdigest=hash_hexdigest)
    # log.debug("There are %i old backup entries for the hash", old_backups.count())
    old_backups = old_backups.exclude(no_link_source=True)
    # log.debug("%i old backup entries with 'no_link_source=False'", old_backups.count())
    for old_backup in old_backups:
        log.debug("+++ old: '%s'", old_backup)

        abs_old_backup_path = old_backup.get_backup_path()
        if not abs_old_backup_path.is_file():
            # e.g.: User has delete a old backup
            old_backup.no_link_source = True  # Don't try this source in future
            old_backup.save()
            continue

        if abs_old_backup_path == backup_entry.path:
            log.warning(f"Skip own file: {abs_old_backup_path}")
            continue

        # TODO: compare hash / current content before replace with a link

        temp_filepath = rename2temp(
            src=backup_entry,
            # Actually we would like to use the current filepath:
            #   dst=path_helper.abs_dst_filepath.parent,
            # But this can result in a error on Windows, because
            # the complete path length is limited to 259 Characters!
            # see:
            #   https://msdn.microsoft.com/en-us/library/aa365247.aspx#maxpath
            # on long path, we will fall into FileNotFoundError:
            #   https://github.com/jedie/PyHardLinkBackup/issues/13#issuecomment-176241894
            # So we use the destination root directory:
            dst=abs_dst_root,
            prefix=f"{backup_entry.name}_",
            suffix=".tmp",
            tmp_max=10,
        )
        log.debug(f"{backup_entry} was renamed to {temp_filepath}")
        try:
            abs_old_backup_path.link(backup_entry)  # call os.link()
        except OSError as err:
            temp_filepath.rename(backup_entry)
            log.error(f"Can't link '{abs_old_backup_path}' to '{backup_entry}': {err}")
            log.info("Mark %r with 'no link source'.", old_backup)
            old_backup.no_link_source = True
            old_backup.save()
        else:
            temp_filepath.unlink()  # FIXME
            log.info(f"Replaced with a hardlink to: '{abs_old_backup_path}'")
            return old_backup
