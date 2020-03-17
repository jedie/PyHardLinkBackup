class BackupFileError(Exception):
    """
    A error occur while backup one file.
    """
    pass


class BackupPathMismatch(Exception):
    """
    Backup file path from "phlb_config.ini" doesn't match with database entry
    """
    pass
