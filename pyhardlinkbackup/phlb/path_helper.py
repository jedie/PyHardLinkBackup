import datetime
import logging
import os
import sys
import tempfile

# https://github.com/jedie/pathlib_revised/
from pathlib_revised import Path2

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.phlb.config import phlb_config

log = logging.getLogger(f"phlb.{__name__}")


def get_tempname(path, prefix="", suffix=""):
    names = tempfile._get_candidate_names()
    for seq in range(tempfile.TMP_MAX):
        name = next(names)
        yield Path2(path, prefix + name + suffix)


def rename2temp(src, dst, prefix="", suffix="", tmp_max=10):
    paths = get_tempname(path=dst, prefix=prefix, suffix=suffix)
    for i in range(tmp_max):
        temp_filepath = next(paths)
        try:
            src.rename(temp_filepath)
        except FileExistsError:
            continue
        else:
            return temp_filepath
    raise OSError(f"Can't find useable temp name! Have tried {tmp_max:d} variants.")


class PathHelper:
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

    def __init__(self, src_path, force_name=None):
        """
        :param src_path: Path2() instance of the source directory
        :param force_name: Force this name for the backup
        """
        self.abs_src_root = Path2(src_path).resolve()
        log.debug(" * abs_src_root: '%s'", self.abs_src_root)

        if not self.abs_src_root.is_dir():
            raise OSError(f"Source path '{self.abs_src_root}' doesn't exists!")

        self.src_prefix_path = self.abs_src_root.parent
        log.debug(" * src_prefix_path: '%s'", self.src_prefix_path)

        self.backup_name = self.abs_src_root.name
        if force_name is not None:
            self.backup_name = force_name
        elif not self.backup_name:
            print("\nError get name for this backup!", file=sys.stderr)
            print("\nPlease use '--name' for force a backup name!\n", file=sys.stderr)
            sys.exit(-1)
        log.debug(" * backup_name: '%s'", self.backup_name)

        self.backup_datetime = datetime.datetime.now()
        self.time_string = self.backup_datetime.strftime(phlb_config.sub_dir_formatter)
        log.debug(" * time_string: %r", self.time_string)

        self.abs_dst_root = Path2(phlb_config.backup_path, self.backup_name, self.time_string)
        log.debug(" * abs_dst_root: '%s'", self.abs_dst_root)

        self.log_filepath = Path2(phlb_config.backup_path, self.backup_name, self.time_string + ".log")
        self.summary_filepath = Path2(phlb_config.backup_path, self.backup_name, self.time_string + " summary.txt")

        # set in set_src_filepath():
        self.abs_src_filepath = None
        self.sub_filepath = None
        self.sub_path = None
        self.filename = None
        self.abs_dst_path = None
        self.abs_dst_filepath = None
        self.abs_dst_hash_filepath = None

    def set_src_filepath(self, src_dir_path):
        """
        Set one filepath to backup this file.
        Called for every file in the source directory.

        :argument src_dir_path: filesystem_walk.DirEntryPath() instance
        """
        log.debug("set_src_filepath() with: '%s'", src_dir_path)
        self.abs_src_filepath = src_dir_path.resolved_path
        log.debug(f" * abs_src_filepath: {self.abs_src_filepath}")

        if self.abs_src_filepath is None:
            log.info("Can't resolve source path: %s", src_dir_path)
            return

        self.sub_filepath = self.abs_src_filepath.relative_to(self.abs_src_root)
        log.debug(f" * sub_filepath: {self.sub_filepath}")

        self.sub_path = self.sub_filepath.parent
        log.debug(f" * sub_path: {self.sub_path}")

        self.filename = self.sub_filepath.name
        log.debug(f" * filename: {self.filename}")

        self.abs_dst_path = Path2(self.abs_dst_root, self.sub_path)
        log.debug(f" * abs_dst_path: {self.abs_dst_path}")

        self.abs_dst_filepath = Path2(self.abs_dst_root, self.sub_filepath)
        log.debug(f" * abs_dst_filepath: {self.abs_dst_filepath}")

        self.abs_dst_hash_filepath = Path2(f"{self.abs_dst_filepath}{os.extsep}{phlb_config.hash_name}")
        log.debug(f" * abs_dst_hash_filepath: {self.abs_dst_hash_filepath}")
