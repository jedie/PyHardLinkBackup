# PyHardLinkBackup

[![tests](https://github.com/jedie/PyHardLinkBackup/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/jedie/PyHardLinkBackup/actions/workflows/tests.yml)
[![codecov](https://codecov.io/github/jedie/PyHardLinkBackup/branch/main/graph/badge.svg)](https://app.codecov.io/github/jedie/PyHardLinkBackup)
[![PyHardLinkBackup @ PyPi](https://img.shields.io/pypi/v/PyHardLinkBackup?label=PyHardLinkBackup%20%40%20PyPi)](https://pypi.org/project/PyHardLinkBackup/)
[![Python Versions](https://img.shields.io/pypi/pyversions/PyHardLinkBackup)](https://github.com/jedie/PyHardLinkBackup/blob/main/pyproject.toml)
[![License GPL-3.0-or-later](https://img.shields.io/pypi/l/PyHardLinkBackup)](https://github.com/jedie/PyHardLinkBackup/blob/main/LICENSE)

HardLink/Deduplication Backups with Python

**WIP:** v1.0.0 is a complete rewrite of PyHardLinkBackup. The new version is not usable, yet!


## concept

### Implementation boundaries

* pure Python using >=3.12
* pathlib for path handling
* iterate filesystem with `os.scandir()`

### overview

* Backups should be saved as normal files in the filesystem:
  * non-proprietary format
  * accessible without any extra software or extra meta files
* Create backups with versioning
  * every backup run creates a complete filesystem snapshot tree
  * every snapshot tree can be deleted, without affecting the other snapshots
* Deduplication with hardlinks:
  * space-efficient incremental backups by linking unchanged files across snapshots instead of duplicating them
  * find duplicate files everywhere (even if renamed or moved files)


### used solutions

* Used `sha256` hash algorithm to identify file content
* Small file handling
  * Always copy small files and never hardlink them
  * Don't store size and hash of these files in the deduplication lookup tables

#### Deduplication lookup methods

To avoid unnecessary file copy operations, we need a fast method to find duplicate files.
Our approach is based on two steps: file size and file content hash.
Because the file size is very fast to compare.

###### size "database"

We store all existing file sizes as empty files in a special folder structure:

  * 1st level: first 2 digits of the size in bytes
  * 2nd level: next 2 digits of the size in bytes
  * file: full size in bytes as filename

e.g.: file size `123456789` bytes stored in: `{destination}/.phlb/size-lookup/89/67/123456789`
We skip files lower than `1000` bytes, so no filling with leading zeros is needed ;)

###### hash "database"

We store the `file hash` <-> `hardlink pointer` mapping in a special folder structure:

  * 1st level: first 2 chars of the hex encoded hash
  * 2nd level: next 2 chars of the hex encoded hash
  * file: full hex encoded hash as filename

e.g.: hash like `abcdef123...` stored in: `{destination}/.phlb/hash-lookup/ab/cd/abcdef123...`
The file contains only the relative path to the first hardlink of this file content.


## CLI - backup command

The main command is `backup`:

[comment]: <> (✂✂✂ auto generated backup help start ✂✂✂)
```
usage: ./cli.py backup [-h] source destination [--excludes STR|{[STR [STR ...]]}] [-v]

Backup the source directory to the destination directory using hard links for deduplication.

╭─ positional arguments ───────────────────────────────────────────────────────────────────────────────────────────────╮
│ source       Source directory to back up. (required)                                                                 │
│ destination  Destination directory for the backup. (required)                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ -h, --help   show this help message and exit                                                                         │
│ --excludes STR|{[STR [STR ...]]}                                                                                     │
│              List of directory or file names to exclude from backup. (default: __pycache__ .cache .temp .tmp .tox    │
│              .nox)                                                                                                   │
│ -v, --verbosity                                                                                                      │
│              Verbosity level; e.g.: -v, -vv, -vvv, etc. (repeatable)                                                 │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
[comment]: <> (✂✂✂ auto generated backup help end ✂✂✂)


## CLI - main app help

[comment]: <> (✂✂✂ auto generated main help start ✂✂✂)
```
usage: ./cli.py [-h] {backup,benchmark-hashes,version}



╭─ options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ -h, --help            show this help message and exit                                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ subcommands ────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ (required)                                                                                                           │
│   • backup            Backup the source directory to the destination directory using hard links for deduplication.   │
│   • benchmark-hashes  Benchmark different file hashing algorithms on the given path Example output:                  │
│                                                                                                                      │
│                       Total files hashed: 220, total size: 1187.7 MiB                                                │
│                                                                                                                      │
│                       Results: Total file content read time: 1.7817s                                                 │
│                                                                                                                      │
│                       sha1       | Total: 0.6827s | 0.4x hash/read sha256     | Total: 0.7189s | 0.4x hash/read      │
│                       sha224     | Total: 0.7375s | 0.4x hash/read sha384     | Total: 1.6552s | 0.9x hash/read      │
│                       blake2b    | Total: 1.6708s | 0.9x hash/read md5        | Total: 1.6870s | 0.9x hash/read      │
│                       sha512     | Total: 1.7269s | 1.0x hash/read shake_128  | Total: 1.9834s | 1.1x hash/read      │
│                       sha3_224   | Total: 2.3006s | 1.3x hash/read sha3_256   | Total: 2.3856s | 1.3x hash/read      │
│                       shake_256  | Total: 2.4375s | 1.4x hash/read blake2s    | Total: 2.5219s | 1.4x hash/read      │
│                       sha3_384   | Total: 3.2596s | 1.8x hash/read sha3_512   | Total: 4.5328s | 2.5x hash/read      │
│   • version           Print version and exit                                                                         │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
[comment]: <> (✂✂✂ auto generated main help end ✂✂✂)


## dev CLI

[comment]: <> (✂✂✂ auto generated dev help start ✂✂✂)
```
usage: ./dev-cli.py [-h] {coverage,install,lint,mypy,nox,pip-audit,publish,shell-completion,test,update,update-readme-history,update-test-snapshot-files,version}



╭─ options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ -h, --help     show this help message and exit                                                                       │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ subcommands ────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ (required)                                                                                                           │
│   • coverage   Run tests and show coverage report.                                                                   │
│   • install    Install requirements and 'PyHardLinkBackup' via pip as editable.                                      │
│   • lint       Check/fix code style by run: "ruff check --fix"                                                       │
│   • mypy       Run Mypy (configured in pyproject.toml)                                                               │
│   • nox        Run nox                                                                                               │
│   • pip-audit  Run pip-audit check against current requirements files                                                │
│   • publish    Build and upload this project to PyPi                                                                 │
│   • shell-completion                                                                                                 │
│                Setup shell completion for this CLI (Currently only for bash shell)                                   │
│   • test       Run unittests                                                                                         │
│   • update     Update dependencies (uv.lock) and git pre-commit hooks                                                │
│   • update-readme-history                                                                                            │
│                Update project history base on git commits/tags in README.md Will be exited with 1 if the README.md   │
│                was updated otherwise with 0.                                                                         │
│                                                                                                                      │
│                Also, callable via e.g.:                                                                              │
│                    python -m cli_base update-readme-history -v                                                       │
│   • update-test-snapshot-files                                                                                       │
│                Update all test snapshot files (by remove and recreate all snapshot files)                            │
│   • version    Print version and exit                                                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
[comment]: <> (✂✂✂ auto generated dev help end ✂✂✂)


## Backwards-incompatible changes

### v1.0.0

v1 is a complete rewrite of PyHardLinkBackup.

## History

[comment]: <> (✂✂✂ auto generated history start ✂✂✂)

* [v1.0.0rc1](https://github.com/jedie/PyHardLinkBackup/compare/v0.13.0...v1.0.0rc1)
  * 2026-01-13 - Rename [project.scripts] hooks
  * 2026-01-13 - Add DocWrite, handle broken symlinks, keep file meta, handle missing hardlink sources
  * 2026-01-12 - First working iteration with rich progess bar
  * 2026-01-08 - Rewrite everything
* [v0.13.0](https://github.com/jedie/PyHardLinkBackup/compare/v0.12.3...v0.13.0)
  * 2020-03-18 - release v0.13.0
  * 2020-03-17 - deactivate pypy tests in travis, because of SQLite errors, like:
  * 2020-03-17 - make CI pipeline easier
  * 2020-03-17 - update README
  * 2020-03-17 - Fix misleading error msg for dst OSError, bad exception handling #23
  * 2020-03-17 - Change Django Admin header
  * 2020-03-17 - Fix "run django server doesn't work" #39
  * 2020-03-17 - test release v0.12.4.rc1
  * 2020-03-17 - Simplify backup process bar update code
  * 2020-03-17 - Bugfix add command if "phlb_config.ini" doesn't match with database entry
  * 2020-03-17 - bugfix "add" command
  * 2020-03-17 - change CHUNK_SIZE in ini config to MIN_CHUNK_SIZE
  * 2020-03-17 - update requirements
  * 2020-03-17 - release v0.12.4.rc0
  * 2020-03-17 - dynamic chunk size
  * 2020-03-17 - ignore *.sha512 by default
  * 2020-03-17 - Update boot_pyhardlinkbackup.sh
* [v0.12.3](https://github.com/jedie/PyHardLinkBackup/compare/v0.12.2...v0.12.3)
  * 2020-03-17 - update README.rst
  * 2020-03-17 - don't publish if tests fail
  * 2020-03-17 - cleanup pytest config
  * 2020-03-17 - Fix "Files to backup" message and update tests
  * 2020-03-16 - Fix #44 - wroing file size in process bar
  * 2020-03-16 - just warn if used directly (needfull for devlopment to call this directly ;)
  * 2020-03-16 - update requirements
  * 2020-03-16 - +pytest-randomly
* [v0.12.2](https://github.com/jedie/PyHardLinkBackup/compare/v0.12.1...v0.12.2)
  * 2020-03-06 - repare v0.12.2 release
  * 2020-03-06 - enhance log file content
  * 2020-03-06 - update requirements
  * 2020-03-06 - Update README.creole
  * 2020-03-05 - Fix #40 by decrease log level
  * 2020-03-05 - Update boot_pyhardlinkbackup.cmd
  * 2020-03-05 - Update boot_pyhardlinkbackup.sh

<details><summary>Expand older history entries ...</summary>

* [v0.12.1](https://github.com/jedie/PyHardLinkBackup/compare/v0.12.0...v0.12.1)
  * 2020-03-05 - update tests and set version to 0.12.1
  * 2020-03-05 - less verbose pytest output
  * 2020-03-05 - pyhardlinkbackup.ini -> PyHardLinkBackup.ini
  * 2020-03-05 - revert renaming the main destination directory back to: "PyHardLinkBackup"
* [v0.12.0](https://github.com/jedie/PyHardLinkBackup/compare/v0.11.0...v0.12.0)
  * 2020-03-05 - repare v0.12.0 release
  * 2020-03-05 - use poetry_publish.tests.test_project_setup code parts
  * 2020-03-05 - Update README.creole
  * 2020-03-05 - renove unused code parts
  * 2020-03-05 - don't test with pypy
  * 2020-03-05 - fix code style
  * 2020-03-05 - Fix tests with different python versions
  * 2020-03-05 - bugfix test: getting manage.py in tox
  * 2020-03-05 - update requirements
  * 2020-03-05 - Don't create "summary" file: log everything in .log file
  * 2020-02-16 - Handle Backup errors.
  * 2020-02-16 - Bugfix processed files count
  * 2020-02-16 - Bugfix: Mark backup run instance as "completed"
  * 2020-02-16 - code cleanup
  * 2020-02-16 - Use assert_is_file() from django-tools and Path().read_text()
  * 2020-02-16 - Don't init a second PathHelper instance!
  * 2020-02-02 - WIP: update Tests
  * 2020-02-02 - run linters as last step
  * 2020-02-02 - remove unused import
  * 2020-02-02 - update IterFilesystem
  * 2020-02-02 - bugfix file size formats
  * 2020-02-02 - stats_helper.abort always exists in newer IterFilesystem version
  * 2020-02-02 - Link or copy the log file to backup and fix summary/output
  * 2020-02-02 - remove converage config from pytest.ini
  * 2020-02-02 - pytest-django: reuse db + nomigrations
  * 2020-02-02 - remove not needed django_project/wsgi.py
  * 2020-02-02 - update README
  * 2020-02-02 - pyhardlinkbackup/{phlb_cli.py => phlb/cli.py}
  * 2020-02-02 - fix Django project setup and add tests for it
  * 2020-02-02 - update Django project settings
  * 2020-02-02 - test release 0.12.0.dev0
  * 2020-02-02 - include poetry.lock file
  * 2020-02-02 - set version to v0.11.0.dev0
  * 2020-02-02 - remove flak8 test (will be done in ci via Makefile)
  * 2020-02-02 - some code updates
  * 2020-02-02 - apply "make fix-code-style"
  * 2020-02-02 - update Makefile: poetry_publish -> pyhardlinkbackup ;)
  * 2020-02-02 - add README.rst
  * 2020-02-02 - /{PyHardLinkBackup => pyhardlinkbackup}/
  * 2020-02-02 - + "make runserver"
  * 2020-02-02 - delete setup.py and setup.cfg
  * 2020-02-02 - WIP: use poetry and poetry-publish
  * 2020-02-02 - update to Django v2.2.x LTS
  * 2019-10-20 - fixup! WIP: update tests
  * 2019-10-20 - +tests_require=['pytest',]
  * 2019-10-20 - update "add" command
  * 2019-10-20 - add setup.cfg
  * 2019-10-13 - use https://github.com/jedie/IterFilesystem
  * 2019-09-18 - remove support for old python versions
  * 2019-09-18 - fix pytest run
  * 2019-03-03 - use pytest + tox and add flake8+isort config files
* [v0.11.0](https://github.com/jedie/PyHardLinkBackup/compare/v0.10.1...v0.11.0)
  * 2019-03-03 - +email
  * 2019-03-03 - use django v1.11.x
  * 2019-03-03 - update django
  * 2019-03-03 - remove: create_dev_env.sh
  * 2019-03-03 - just code formatting with black
  * 2019-03-03 - update setup.py
  * 2019-03-03 - +create_dev_env.sh
  * 2018-09-12 - Update boot_pyhardlinkbackup.cmd
  * 2018-08-03 - Update phlb_run_tests.sh
  * 2018-08-03 - Update phlb_upgrade_PyHardLinkBackup.sh
  * 2017-12-11 - code cleanup
  * 2017-12-10 - Update boot_pyhardlinkbackup.sh
  * 2017-12-10 - set DJANGO_SETTINGS_MODULE
  * 2017-11-17 - +codecov.io
* [v0.10.1](https://github.com/jedie/PyHardLinkBackup/compare/v0.10.0...v0.10.1)
  * 2016-09-09 - fix #24 by skip not existing files
  * 2016-08-20 - fix typos, improve grammar, add borgbackup
  * 2016-06-28 - use the origin model to use the config methods:
  * 2016-06-27 - use get_model()
  * 2016-06-27 - add missing migrations for:
  * 2016-04-28 - Update README.creole
  * 2016-04-27 - bugfix ~/
* [v0.10.0](https://github.com/jedie/PyHardLinkBackup/compare/v0.9.0...v0.10.0)
  * 2016-04-27 - -%APPDATA% +%ProgramFiles%
  * 2016-04-26 - v0.9.1
  * 2016-04-26 - bugfix boot cmd
  * 2016-04-26 - add note
  * 2016-04-26 - migrate after boot
  * 2016-04-26 - add migrate scripts
  * 2016-03-08 - bugfix if path contains spaces
  * 2016-02-29 - Update README.creole
* [v0.9.0](https://github.com/jedie/PyHardLinkBackup/compare/v0.8.0...v0.9.0)
  * 2016-02-10 - v0.9.0
  * 2016-02-10 - fix AppVeyor
  * 2016-02-10 - fix path?
  * 2016-02-10 - add pathlib_revised
  * 2016-02-10 - typo
  * 2016-02-08 - try to combine linux and windows tests coverage via:
  * 2016-02-08 - move Path2() to external lib: https://github.com/jedie/pathlib_revised
  * 2016-02-08 - Use existing hash files in "phlb add" command:
  * 2016-02-08 - Work-a-round for Windows MAX_PATH limit: Use \?\ path prefix internally.
* [v0.8.0](https://github.com/jedie/PyHardLinkBackup/compare/v0.7.0...v0.8.0)
  * 2016-02-04 - release v0.8.0
  * 2016-02-04 - seems that windows/NTFS is less precise ;)
  * 2016-02-04 - tqdm will not accept 0 bytes files ;)
  * 2016-02-04 - new: "phlb add"
  * 2016-02-04 - bugfix: display skip pattern info
* [v0.7.0](https://github.com/jedie/PyHardLinkBackup/compare/v0.6.4...v0.7.0)
  * 2016-02-03 - release v0.7.0
  * 2016-02-03 - remove obsolete cli command and update cli unittests
  * 2016-02-03 - do 'migrate' on every upgrade run, too.
  * 2016-02-03 - Update README.creole
  * 2016-02-03 - Fix: #17 and save a "phlb_config.ini" in every backup:
  * 2016-02-02 - New: verify a existing backup
  * 2016-02-02 - remove editable=False
* [v0.6.4](https://github.com/jedie/PyHardLinkBackup/compare/v0.6.3...v0.6.4)
  * 2016-02-01 - v0.6.4
  * 2016-02-01 - prepare for v0.6.4 release
  * 2016-02-01 - Fix #13 - temp rename error, because of the Windows API limitation
  * 2016-01-31 - bugfix in scanner if symlink is broken
  * 2016-01-31 - display local variables on low level errors
* [v0.6.3](https://github.com/jedie/PyHardLinkBackup/compare/v0.6.2...v0.6.3)
  * 2016-01-29 - Less verbose and better information about SKIP_DIRS/SKIP_PATTERNS hits
  * 2016-01-29 - error -> info
  * 2016-01-29 - +keywords +license
* [v0.6.2](https://github.com/jedie/PyHardLinkBackup/compare/v0.6.1...v0.6.2)
  * 2016-01-29 - fix tests by change the mtime of the test files to get always the same order
  * 2016-01-28 - Handle unexpected errors and KeyboardInterrupt
* [v0.6.1](https://github.com/jedie/PyHardLinkBackup/compare/v0.6.0...v0.6.1)
  * 2016-01-28 - release v0.6.1
  * 2016-01-28 - fix #13 by use a better rename routine
* [v0.6.0](https://github.com/jedie/PyHardLinkBackup/compare/v0.5.1...v0.6.0)
  * 2016-01-28 - start maring the admin nicer, see also: #7
  * 2016-01-28 - faster backup by compare mtime/size only if old backup files exists
* [v0.5.1](https://github.com/jedie/PyHardLinkBackup/compare/v0.5.0...v0.5.1)
  * 2016-01-27 - Squashed commit of the following:
* [v0.5.0](https://github.com/jedie/PyHardLinkBackup/compare/v0.4.2...v0.5.0)
  * 2016-01-27 - release v0.5.0
  * 2016-01-27 - refactory source tree scan and use pathlib everywhere:
  * 2016-01-24 - try to fix DB memory usage
  * 2016-01-24 - Simulate not working os.link with mock
  * 2016-01-24 - fix if duration==0
  * 2016-01-24 - use mock to simulate not readable files
  * 2016-01-24 - just move class
  * 2016-01-23 - fix #10 and add --name cli argument and add unittests for the changes
  * 2016-01-23 - alternative solutions
* [v0.4.2](https://github.com/jedie/PyHardLinkBackup/compare/v0.4.1...v0.4.2)
  * 2016-01-22 - work-a-round for junction under windows
  * 2016-01-22 - Display if out path can't created
  * 2016-01-22 - print some more status information in between.
  * 2016-01-22 - Update README.creole
  * 2016-01-22 - typo
  * 2016-01-22 - try to reproduce #11
  * 2016-01-22 - check if test settings are active
  * 2016-01-22 - needless
  * 2016-01-22 - importand to change into current directory for:
* [v0.4.1](https://github.com/jedie/PyHardLinkBackup/compare/v0.4.0...v0.4.1)
  * 2016-01-21 - merge get log content and fix windows tests
  * 2016-01-21 - Skip files that can't be read/write
  * 2016-01-21 - Update README.creole
* [v0.4.0](https://github.com/jedie/PyHardLinkBackup/compare/v0.3.1...v0.4.0)
  * 2016-01-21 - save summary and log file for every backup run
  * 2016-01-21 - increase default chunk size to 20MB
  * 2016-01-21 - typo
  * 2016-01-21 - moved TODO:
  * 2016-01-21 - journal_mode = MEMORY
  * 2016-01-21 - wip
  * 2016-01-21 - bugfix: use pathlib instance
  * 2016-01-21 - activate py3.4 32bit tests
  * 2016-01-21 - update
  * 2016-01-21 - Bugfix for python < 3.5
  * 2016-01-16 - WIP: Bugfix unittests for: Change .ini search path to every parent directory WIP: Save summary and log file for every backup run
  * 2016-01-16 - Change .ini search path to every parent directory
  * 2016-01-16 - Add a unittest for the NTFS 1024 hardlink limit
  * 2016-01-15 - bugfix if unittests failed under appveyor
  * 2016-01-15 - change timestamp stuff in unittests
  * 2016-01-15 - Update README.creole
  * 2016-01-15 - Create WindowsDevelopment.creole
* [v0.3.1](https://github.com/jedie/PyHardLinkBackup/compare/v0.3.0...v0.3.1)
  * 2016-01-15 - v0.3.1
  * 2016-01-15 - try to fix 'coveralls':
  * 2016-01-15 - ignore temp cleanup error
  * 2016-01-15 - fix some unittests under windows:
  * 2016-01-15 - obsolete
* [v0.3.0](https://github.com/jedie/PyHardLinkBackup/compare/v0.2.0...v0.3.0)
  * 2016-01-15 - release v0.3.0
  * 2016-01-14 - Squashed commit of the following:
* [v0.2.0](https://github.com/jedie/PyHardLinkBackup/compare/v0.1.13...v0.2.0)
  * 2016-01-13 - fix appveyor
  * 2016-01-13 - Refactoring unitests and add more tests
* [v0.1.13](https://github.com/jedie/PyHardLinkBackup/compare/v0.1.12...v0.1.13)
  * 2016-01-12 - 0.1.13
  * 2016-01-11 - set python versions
  * 2016-01-11 - test oder versions
  * 2016-01-11 - print path with %s and not with %r
  * 2016-01-11 - start backup unittests
  * 2016-01-11 - wip
  * 2016-01-11 - wip: fix CI
  * 2016-01-11 - own tests run with :memory: database in temp dir
  * 2016-01-11 - wtf
  * 2016-01-11 - wip: fix appveyor
  * 2016-01-11 - Update README.creole
  * 2016-01-11 - Fix appveyor
  * 2016-01-11 - bugfix
* [v0.1.12](https://github.com/jedie/PyHardLinkBackup/compare/v0.1.11...v0.1.12)
  * 2016-01-11 - 0.1.12
  * 2016-01-11 - unify .cmd files
  * 2016-01-11 - update
  * 2016-01-11 - use "phlb.exe helper" and merge code
  * 2016-01-11 - bugfix
  * 2016-01-11 - Appveyor work-a-round
  * 2016-01-11 - +cmd_shell.cmd
* [v0.1.11](https://github.com/jedie/PyHardLinkBackup/compare/v0.1.10...v0.1.11)
  * 2016-01-10 - wip
  * 2016-01-10 - cd checkout dir
  * 2016-01-10 - don't wait for user input
  * 2016-01-10 - appveyor.yml
  * 2016-01-10 - fix travis CI?
  * 2016-01-10 - test 'py'
  * 2016-01-10 - update boot
  * 2016-01-10 - +migrate
  * 2016-01-10 - try to use the own boot script
  * 2016-01-10 - +# http://www.appveyor.com
  * 2016-01-10 - add badge icons
  * 2016-01-10 - coveralls token
  * 2016-01-10 - migrate database
  * 2016-01-10 - abs path to work?
  * 2016-01-10 - fix?
  * 2016-01-10 - test local .ini change config
  * 2016-01-10 - travis
  * 2016-01-10 - debug config
  * 2016-01-10 - bugfix extras_require
  * 2016-01-10 - simple cli output test
  * 2016-01-10 - refactor cli and start travis CI
  * 2016-01-10 - install scandir via extras_require
* [v0.1.10](https://github.com/jedie/PyHardLinkBackup/compare/v0.1.9...v0.1.10)
  * 2016-01-10 - v0.1.10
  * 2016-01-10 - cleanup after KeyboardInterrupt
  * 2016-01-10 - always activate venv
  * 2016-01-10 - shell scripts for linux
  * 2016-01-10 - update README
  * 2016-01-10 - add boot script for linux
* [v0.1.9](https://github.com/jedie/PyHardLinkBackup/compare/v0.1.8...v0.1.9)
  * 2016-01-08 - Helper files for Windows:
  * 2016-01-08 - Update setup.py
  * 2016-01-08 - Update README.creole
* [v0.1.8](https://github.com/jedie/PyHardLinkBackup/compare/v0.1.7...v0.1.8)
  * 2016-01-08 - django reloaded will not work under windows with venv
  * 2016-01-08 - create more batch helper files
  * 2016-01-08 - work-a-round for path problem under windows.
* [v0.1.7](https://github.com/jedie/PyHardLinkBackup/compare/v0.1.6...v0.1.7)
  * 2016-01-08 - bugfix line endings in config file
* [v0.1.6](https://github.com/jedie/PyHardLinkBackup/compare/v0.1.5...v0.1.6)
  * 2016-01-08 - remove checks: doesn't work with py3 venv
* [v0.1.5](https://github.com/jedie/PyHardLinkBackup/compare/v0.1.4...v0.1.5)
  * 2016-01-08 - add "pip upgrade" batch
  * 2016-01-08 - bugfix to include the default config ini file ;)
* [v0.1.4](https://github.com/jedie/PyHardLinkBackup/compare/v0.1.3...v0.1.4)
  * 2016-01-07 - update windows boot file
  * 2016-01-07 - include .ini files
  * 2016-01-07 - rename
* [v0.1.3](https://github.com/jedie/PyHardLinkBackup/compare/v0.1.2...v0.1.3)
  * 2016-01-07 - remove 'scandir' from 'install_requires'
* [v0.1.2](https://github.com/jedie/PyHardLinkBackup/compare/v0.1.1...v0.1.2)
  * 2016-01-07 - install and use "scandir" only if needed
* [v0.1.1](https://github.com/jedie/PyHardLinkBackup/compare/629bc4f...v0.1.1)
  * 2016-01-07 - fix headline levels (for reSt)
  * 2016-01-07 - start boot script for windows
  * 2016-01-07 - v0.1.1
  * 2016-01-07 - refactory .ini config usage
  * 2016-01-07 - WIP: Use .ini file for base config
  * 2016-01-07 - Update README.creole
  * 2016-01-06 - move database to ~/PyHardLinkBackups.sqlite3
  * 2016-01-06 - PyHardlinkBackup -> PyHardLinkBackup
  * 2016-01-06 - +.idea
  * 2016-01-06 - Refactor:
  * 2016-01-06 - add a auto login to django admin with auto created default user
  * 2016-01-06 - nicer output
  * 2016-01-06 - Use database to deduplicate
  * 2016-01-06 - add human time
  * 2016-01-06 - add dev reset script
  * 2016-01-06 - force DJANGO_SETTINGS_MODULE
  * 2016-01-06 - Display shortend hash and add filesize
  * 2016-01-04 - refactor django stuff
  * 2016-01-04 - add some meta files
  * 2016-01-04 - start using django
  * 2016-01-03 - use https://pypi.python.org/pypi/scandir as fallback
  * 2015-12-29 - Create README.creole
  * 2015-12-29 - Create proof_of_concept.py
  * 2015-12-29 - Initial commit

</details>


[comment]: <> (✂✂✂ auto generated history end ✂✂✂)
