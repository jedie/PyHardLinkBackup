import datetime
import os

from PyHardLinkBackup.backup_app.models import BackupRun
from PyHardLinkBackup.phlb.config import phlb_config
from PyHardLinkBackup.phlb.phlb_main import log


class PathHelper(object):
    """
    e.g.: backup run called with: /abs/source/path/source_root

    |<---------self.abs_src_filepath------------->|
    |                                             |
    |<--self.abs_src_root-->|<-self.sub_filepath->|
    |                          |                  |
    /abs/source/path/source_root/sub/path/filename
    |              | |         | |      | |      |
    +-------------'  +--------'  +-----'  +-----'
    |                |           |        |
    |                |           |        `-> self.filename
    |                |           `-> self.sub_path
    |                `-> self.backup_name (root dir to backup)
    `-> self.src_prefix_path

    |<---------self.abs_dst_filepath------------------>|
    |                                                  |
    |<----self.abs_dst_root----->|<-self.sub_filepath->|
    |                            |                     |
    |<---------self.abs_dst_path-+------->|        .---'
    |                            |        |        |
    /abs/destination/name/datetime/sub/path/filename
    |-------------'  |-'  |-----'  |-----'  |-----'
    |                |    |        |        `-> self.filename
    |                |    |        `-> self.sub_path
    |                |    `-> self.time_string (Start time of the backup run)
    |                `<- self.backup_name
    `- phlb_config.backup_path (root dir storage for all backups runs)
    """
    def __init__(self, src_path):
        self.abs_src_root = self.abs_norm_path(src_path)
        log.debug(" * abs_src_root: '%s'", self.abs_src_root)

        if not os.path.isdir(self.abs_src_root):
            raise OSError("Source path '%s' doesn't exists!" % self.abs_src_root)

        self.src_prefix_path, self.backup_name = os.path.split(self.abs_src_root)
        log.debug(" * src_prefix_path: '%s'", self.src_prefix_path)
        log.debug(" * backup_name: '%s'", self.backup_name)

        backup_datetime = datetime.datetime.now()
        self.time_string = backup_datetime.strftime(phlb_config.sub_dir_formatter)
        log.debug(" * time_string: %r", self.time_string)

        self.abs_dst_root = os.path.join(phlb_config.backup_path, self.backup_name, self.time_string)
        log.debug(" * abs_dst_root: '%s'", self.abs_dst_root)

        self.log_filepath = os.path.join(phlb_config.backup_path, self.backup_name, self.time_string+".log")
        self.summary_filepath = os.path.join(phlb_config.backup_path, self.backup_name, self.time_string+" summary.txt")

        self.backup_run = BackupRun.objects.create(
            name = self.backup_name,
            backup_datetime=backup_datetime
        )
        log.debug(" * backup_run: %s" % self.backup_run)

        # set in set_src_filepath():
        self.abs_src_filepath = None
        self.sub_filepath = None
        self.sub_path = None
        self.filename = None
        self.abs_dst_path = None
        self.abs_dst_filepath = None
        self.abs_dst_hash_filepath = None

    def set_src_filepath(self, src_filepath):
        """
        Set one filepath to backup this file.
        Called for every file in the source directory.
        """
        log.debug("set_src_filepath() with: '%s'", src_filepath)
        self.abs_src_filepath = self.abs_norm_path(src_filepath)
        log.debug(" * abs_src_filepath: %s" % self.abs_src_filepath)

        # FIXME:
        assert self.abs_src_filepath.startswith(self.abs_src_root)
        self.sub_filepath = self.abs_src_filepath[len(self.abs_src_root):]
        self.sub_filepath = self.sub_filepath.lstrip(os.sep)
        log.debug(" * sub_filepath: %s" % self.sub_filepath)

        self.sub_path, self.filename = os.path.split(self.sub_filepath)
        log.debug(" * sub_path: %s" % self.sub_path)
        log.debug(" * filename: %s" % self.filename)

        self.abs_dst_path = os.path.join(self.abs_dst_root, self.sub_path)
        log.debug(" * abs_dst_path: %s" % self.abs_dst_path)

        self.abs_dst_filepath = os.path.join(self.abs_dst_root, self.sub_filepath)
        log.debug(" * abs_dst_filepath: %s" % self.abs_dst_filepath)

        self.abs_dst_hash_filepath = self.abs_dst_filepath + os.extsep + phlb_config.hash_name
        log.debug(" * abs_dst_hash_filepath: %s" % self.abs_dst_hash_filepath)

    def abs_norm_path(self, path):
        return os.path.normpath(os.path.abspath(os.path.expanduser(path)))
