#!/usr/bin/python3

"""
    Python HardLink Backup
    ~~~~~~~~~~~~~~~~~~~~~~

    **WARNING: needs Python >=3.5 !

    :copyleft: 2015 by Jens Diemer
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""

import os
import sys
import time
import datetime
import hashlib

# time.clock() on windows and time.time() on linux
from timeit import default_timer


#~ DEFAULT_NEW_PATH_MODE=0o777
DEFAULT_NEW_PATH_MODE=0o700

BACKUP_SUB_FORMAT="%Y-%m-%d-%H%M%S"
CHUNK_SIZE = 64*1024

hash_constructor = hashlib.sha512
HAST_FILE_EXT = ".sha512"


class Hasher(object):
    def __init__(self, ):
        super(Hasher, self).__init__()
        self["md5"] = hashlib.md5()
        self["sha1"] = hashlib.sha1()
        self["sha256"] = hashlib.sha256()

    def update(self, data):
        self["md5"].update(data)
        self["sha1"].update(data)
        self["sha256"].update(data)




class PathHelper(object):
    def __init__(self, backup_root):
        self.backup_root = self.abs_norm_path(backup_root)
        print("backup_root: %r" % self.backup_root)

        self.old_backups = [] # all existing old backups dirs

        self.src_path_raw = None # Source path to backup
        self.dst_path = None # destination in backup without timestamp
        self.src_path_dst = None # destination in backup with timestamp sub dir

        # path information for a file to backup:
        self.abs_src_filepath = None # absolute source filepath
        self.rel_src_filepath = None # relative source filepath
        self.abs_dst_filepath = None # absolute destination in the backup tree
        self.abs_dst_filepath_hash = None # hash filepath in destination
        self.abs_dst_dir = None # absolute destination for the current file in the backup tree

    def collect_old_backups(self):
        assert self.dst_path is not None

        for entry in os.scandir(self.dst_path):
            if entry.is_dir():
                self.old_backups.append(entry)

        print("Found %i existing old backups:" % len(self.old_backups))
        self.old_backups.sort(key=lambda entry: entry.stat().st_mtime, reverse=True)
        for entry in self.old_backups:
            print("\t* %s" % entry.name)

    def iter_old_backup(self):
        assert self.rel_src_filepath is not None

        for entry in self.old_backups:
            old_path = os.path.join(entry.path, self.rel_src_filepath)
            #~ print("\t* %s" % old_path)
            if os.path.isfile(old_path):
                yield old_path, old_path + HAST_FILE_EXT

    def set_src_path(self, raw_path):
        src_path = self.src_path_raw = os.path.normpath(os.path.abspath(raw_path))
        print("src_path_raw: %r" % self.src_path_raw)
        if not os.path.isdir(src_path):
            raise OSError("Source path %r doesn't exists!" % src_path)

        if sys.platform.startswith("win"):
            src_path = os.path.splitdrive(src_path)[1]
            src_path = src_path.lstrip(os.sep)

        self.dst_path = os.path.join(self.backup_root, src_path)
        self.collect_old_backups()

        now = datetime.datetime.now()
        date_string = now.strftime(BACKUP_SUB_FORMAT)

        self.src_path_dst = os.path.join(self.dst_path, date_string)
        print("src_path_dst: %r" % self.src_path_dst)

    def set_src_filepath(self, src_filepath):
        self.abs_src_filepath = self.abs_norm_path(src_filepath)

        # FIXME:
        assert self.abs_src_filepath.startswith(self.src_path_raw)
        self.rel_src_filepath = self.abs_src_filepath[len(self.src_path_raw):].lstrip(os.sep)

        self.abs_dst_filepath = os.path.join(self.src_path_dst, self.rel_src_filepath)
        self.abs_dst_filepath_hash = self.abs_dst_filepath + HAST_FILE_EXT
        self.abs_dst_dir = os.path.split(self.abs_dst_filepath)[0]

    def abs_norm_path(self, path):
        return os.path.normpath(os.path.abspath(path))



def walk2(top, followlinks=False):
    """
    Same as os.walk() except:
     - returns os.scandir() result (os.DirEntry() instance) and not entry.name
     - always topdown=True
    """
    dirs = []
    nondirs = []

    # We may not have read permission for top, in which case we can't
    # get a list of the files the directory contains.  os.walk
    # always suppressed the exception then, rather than blow up for a
    # minor reason when (say) a thousand readable directories are still
    # left to visit.  That logic is copied here.
    try:
        scandir_it = os.scandir(top)
    except OSError:
        return

    while True:
        try:
            try:
                entry = next(scandir_it)
            except StopIteration:
                break
        except OSError:
            return

        try:
            is_dir = entry.is_dir()
        except OSError:
            # If is_dir() raises an OSError, consider that the entry is not
            # a directory, same behaviour than os.path.isdir().
            is_dir = False

        if is_dir:
            dirs.append(entry)
        else:
            nondirs.append(entry)

    yield top, dirs, nondirs

    # Recurse into sub-directories
    islink = os.path.islink
    for entry in dirs:
        # Issue #23605: os.path.islink() is used instead of caching
        # entry.is_symlink() result during the loop on os.scandir() because
        # the caller can replace the directory entry during the "yield"
        # above.
        if followlinks or not islink(entry.path):
            yield from walk2(entry.path, followlinks)


class FileBackup(object):
    def __init__(self, file_entry, backup_path):
        self.file_entry = file_entry # os.DirEntry() instance
        self.backup_path = backup_path # PathHelper(backup_root) instance

    def _deduplication_backup(self, file_entry, in_file, out_file):
        file_size = os.stat(file_entry.path).st_size
        time_threshold = start_time = default_timer()

        bytesreaded = old_readed = 0
        threshold = file_size / 10
        hash = hash_constructor()
        while True:
            data = in_file.read(CHUNK_SIZE)
            if not data:
                break

            out_file.write(data)
            hash.update(data)

            bytesreaded += len(data)

            current_time = default_timer()
            if current_time > (time_threshold + 0.5):

                elapsed = float(current_time - start_time)
                estimated = elapsed / bytesreaded * file_size
                remain = estimated - elapsed

                diff_bytes = bytesreaded - old_readed
                diff_time = current_time - time_threshold
                performance = diff_bytes / diff_time / 1024.0 / 1024.0

                percent = round(float(bytesreaded) / file_size * 100.0, 2)

                infoline = (
                    "   "
                    "%(percent).1f%%"
                    " - current: %(elapsed)s"
                    " - total: %(estimated)s"
                    " - remain: %(remain)s"
                    " - %(perf).1fMB/sec"
                    "   "
                ) % {
                    "percent"  : percent,
                    "elapsed"  : human_time(elapsed),
                    "estimated": human_time(estimated),
                    "remain"   : human_time(remain),
                    "perf"     : performance,
                }
                sys.stdout.write("\r")
                sys.stdout.write("\r{:^79}".format(infoline))

                time_threshold = current_time
                old_readed = bytesreaded

        end_time = default_timer()
        try:
            performance = float(file_size) / (end_time - start_time) / 1024 / 1024
        except ZeroDivisionError as err:
            print("Warning: %s" % err)
            print(end_time, start_time, (end_time - start_time))

        sys.stdout.write("\r")
        sys.stdout.write(" "*79)
        sys.stdout.write("\r")

        print("Performance: %.1fMB/sec" % performance)
        return hash

    def deduplication_backup(self):
        src_path = self.file_entry.path
        print("*** deduplication backup: %r" % src_path)

        self.backup_path.set_src_filepath(src_path)
        print("abs_src_filepath:", self.backup_path.abs_src_filepath)
        print("abs_dst_filepath:", self.backup_path.abs_dst_filepath)
        print("abs_dst_filepath_hash:", self.backup_path.abs_dst_filepath_hash)
        print("abs_dst_dir:", self.backup_path.abs_dst_dir)

        if not os.path.isdir(self.backup_path.abs_dst_dir):
            os.makedirs(self.backup_path.abs_dst_dir, mode=DEFAULT_NEW_PATH_MODE)
        else:
            assert not os.path.isfile(self.backup_path.abs_dst_filepath)

        try:
            with open(self.backup_path.abs_src_filepath, "rb") as in_file:
                with open(self.backup_path.abs_dst_filepath_hash, "w") as hash_file:
                    with open(self.backup_path.abs_dst_filepath, "wb") as out_file:
                        hash = self._deduplication_backup(self.file_entry, in_file, out_file)
                    hash_hexdigest = hash.hexdigest()
                    hash_file.write(hash_hexdigest)
        except KeyboardInterrupt:
            os.remove(dst_path)

        for old_backup, old_hash in self.backup_path.iter_old_backup():
            print("old:", old_backup, old_hash)
            with open(old_hash, "r") as old_hash_file:
                old_hash_value = old_hash_file.read()
            if old_hash_value == hash_hexdigest:
                print("***Found old version in Backup...", end="")
                os.remove(self.backup_path.abs_dst_filepath)
                os.link(old_backup, self.backup_path.abs_dst_filepath)
                print("Remove and link, ok.")
                break
            else:
                print("%r != %r" % (old_hash_value, hash_hexdigest))


class HardLinkBackup(object):
    def __init__(self, backup_root):
        self.path = PathHelper(backup_root)

        os.makedirs(self.path.backup_root, mode=DEFAULT_NEW_PATH_MODE, exist_ok=True)
        if not os.path.isdir(self.path.backup_root):
            raise OSError("Backup path %r doesn't exists!" % self.path.backup_root)

    def scandir(self, path):
        next_update = time.time()+1
        file_list = []
        total_size = 0
        for top, dirs, nondirs in walk2(path):
            for entry in nondirs:
                if entry.is_file():
                    file_list.append(entry)
                    total_size += entry.stat().st_size
                else:
                    raise NotImplementedError("todo: %r" % entry)

            if time.time()>next_update:
                print("%i dir items readed..." % len(file_list))
                next_update = time.time() + 1
        return file_list, total_size

    def backup(self, src_path):
        self.path.set_src_path(src_path)
        print("Backup %r to %r..." % (self.path.src_path_raw, self.path.src_path_dst))

        file_list, total_size = self.scandir(self.path.src_path_raw)
        print("%i files (%i Bytes) to backup." % (len(file_list), total_size))

        backuped_size=0
        for no, file_entry in enumerate(file_list):
            print(no, file_entry.path)

            file_backup = FileBackup(file_entry, self.path)
            file_backup.deduplication_backup()





if __name__ == '__main__':
    backup_root = "d:\PyHardLinkBackups"

    hardlinkbackup = HardLinkBackup(backup_root = backup_root)

    hardlinkbackup.backup(src_path=os.getcwd())
