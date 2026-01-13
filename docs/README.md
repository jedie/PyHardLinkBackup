# PyHardLinkBackup

HardLink/Deduplication Backups with Python

## FileHashDatabase

A simple "database" to store file content hash <-> relative path mappings.
Uses a directory structure to avoid too many files in a single directory.
Path structure:
        {base_dst}/.phlb/hash-lookup/{XX}/{YY}/{hash}
e.g.:
    hash '12ab000a1b2c3...' results in: {base_dst}/.phlb/hash-lookup/12/ab/12ab000a1b2c3...

Notes:
  * Hash length will be not validated, so it can be used with any hash algorithm.
  * The "relative path" that will be stored is not validated, so it can be any string.
  * We don't "cache" anything in Memory, to avoid high memory consumption for large datasets.

## FileHashDatabase - Missing hardlink target file

If a hardlink source from a old backup is missing, we cannot create a hardlink to it.
But it still works to hardlink same files within the current backup.

We check if the hardlink source file still exists. If not, we remove the hash entry from the database.
A warning is logged in this case.

## FileSizeDatabase

A simple "database" to track which file sizes have been seen.

Uses a directory structure to avoid too many files in a single directory.
We don't "cache" anything in Memory, to avoid high memory consumption for large datasets.

Path structure:
 * `{base_dst}/.phlb/size-lookup/{XX}/{YY}/{size}`

e.g.:

 * `1234567890` results in: `{base_dst}/.phlb/size-lookup/12/34/1234567890`

All files are created empty, as we only care about their existence.

## FileSizeDatabase - minimum file size

The minimum file size that can be stored in the FileSizeDatabase is 1000 bytes.
This is because no padding is made for sizes below 1000 bytes, which would
break the directory structure.

The idea is, that it's more efficient to backup small files directly, instead of
checking for duplicates via hardlinks. Therefore, small files below this size
are not tracked in the FileSizeDatabase.

## backup implementation - Symlinks

Symlinks are copied as symlinks in the backup.

Symlinks are not stored in our FileHashDatabase, because they are not considered for hardlinking.