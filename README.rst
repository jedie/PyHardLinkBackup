----------------
pyhardlinkbackup
----------------

Hardlink/Deduplication Backups with Python.

* Backups should be saved as normal files in the filesystem:

    * accessible without any extra software or extra meta files

    * non-proprietary format

* Create backups with versioning

    * every backup run creates a complete filesystem snapshot tree

    * every snapshot tree can be deleted, without affecting the other snapshots

* Deduplication with hardlinks:

    * Store only changed files, all other via hardlinks

    * find duplicate files everywhere (even if renamed or moved files)

* useable under Windows and Linux

Requirement: Python 3.6 or newer.

Please: try, fork and contribute! ;)

+--------------------------------------+------------------------------------------------------------+
| |Build Status on github|             | `github.com/jedie/pyhardlinkbackup/actions`_               |
+--------------------------------------+------------------------------------------------------------+
| |Build Status on travis-ci.org|      | `travis-ci.org/jedie/pyhardlinkbackup`_                    |
+--------------------------------------+------------------------------------------------------------+
| |Build Status on appveyor.com|       | `ci.appveyor.com/project/jedie/pyhardlinkbackup`_          |
+--------------------------------------+------------------------------------------------------------+
| |Coverage Status on coveralls.io|    | `coveralls.io/r/jedie/pyhardlinkbackup`_                   |
+--------------------------------------+------------------------------------------------------------+
| |Requirements Status on requires.io| | `requires.io/github/jedie/pyhardlinkbackup/requirements/`_ |
+--------------------------------------+------------------------------------------------------------+

.. |Build Status on github| image:: https://github.com/jedie/pyhardlinkbackup/workflows/test/badge.svg?branch=master
.. _github.com/jedie/pyhardlinkbackup/actions: https://github.com/jedie/pyhardlinkbackup/actions
.. |Build Status on travis-ci.org| image:: https://travis-ci.org/jedie/pyhardlinkbackup.svg
.. _travis-ci.org/jedie/pyhardlinkbackup: https://travis-ci.org/jedie/pyhardlinkbackup/
.. |Build Status on appveyor.com| image:: https://ci.appveyor.com/api/projects/status/py5sl38ql3xciafc?svg=true
.. _ci.appveyor.com/project/jedie/pyhardlinkbackup: https://ci.appveyor.com/project/jedie/pyhardlinkbackup/history
.. |Coverage Status on coveralls.io| image:: https://coveralls.io/repos/jedie/pyhardlinkbackup/badge.svg
.. _coveralls.io/r/jedie/pyhardlinkbackup: https://coveralls.io/r/jedie/pyhardlinkbackup
.. |Requirements Status on requires.io| image:: https://requires.io/github/jedie/pyhardlinkbackup/requirements.svg?branch=master
.. _requires.io/github/jedie/pyhardlinkbackup/requirements/: https://requires.io/github/jedie/pyhardlinkbackup/requirements/

-------
Example
-------

::

    $ phlb backup ~/my/important/documents
    ...start backup, some time later...
    $ phlb backup ~/my/important/documents
    ...

This will create deduplication backups like this:

::

    ~/pyhardlinkbackups
      └── documents
          ├── 2016-01-07-085247
          │   ├── phlb_config.ini
          │   ├── spreadsheet.ods
          │   ├── brief.odt
          │   └── important_files.ext
          └── 2016-01-07-102310
              ├── phlb_config.ini
              ├── spreadsheet.ods
              ├── brief.odt
              └── important_files.ext

------------
Installation
------------

Windows
=======

#. install Python 3: `https://www.python.org/downloads/ <https://www.python.org/downloads/>`_

#. Download the file `boot_pyhardlinkbackup.cmd <https://raw.githubusercontent.com/jedie/pyhardlinkbackup/master/boot_pyhardlinkbackup.cmd>`_

#. call **boot_pyhardlinkbackup.cmd** as admin (Right-click and use **Run as administrator**)

If everything works fine, you will get a venv here: ``%ProgramFiles%\PyHardLinkBackup``

After the venv is created, call these scripts to finalize the setup:

#. ``%ProgramFiles%\PyHardLinkBackup\phlb_edit_config.cmd`` - create a config .ini file

#. ``%ProgramFiles%\PyHardLinkBackup\phlb_migrate_database.cmd`` - create database tables

To upgrade pyhardlinkbackup, call:

#. ``%ProgramFiles%\PyHardLinkBackup\phlb_upgrade_pyhardlinkbackup.cmd``

To start the Django webserver, call:

#. ``%ProgramFiles%\PyHardLinkBackup\phlb_run_django_webserver.cmd``

Linux
=====

#. Download the file `boot_pyhardlinkbackup.sh <https://raw.githubusercontent.com/jedie/pyhardlinkbackup/master/boot_pyhardlinkbackup.sh>`_

#. call **boot_pyhardlinkbackup.sh**

If everything works fine, you will get a venv here: ``~\pyhardlinkbackup``

After the venv is created, call these scripts to finalize the setup:

* ``~/PyHardLinkBackup/phlb_edit_config.sh`` - create a config .ini file

* ``~/PyHardLinkBackup/phlb_migrate_database.sh`` - create database tables

To upgrade pyhardlinkbackup, call:

* ``~/PyHardLinkBackup/phlb_upgrade_pyhardlinkbackup.sh``

To start the Django webserver, call:

* ``~/PyHardLinkBackup/phlb_run_django_webserver.sh``

---------------------
Starting a backup run
---------------------

To start a backup run, use this helper script:

* Windows batch: ``%ProgramFiles%\PyHardLinkBackup\pyhardlinkbackup_this_directory.cmd``

* Linux shell script: ``~/PyHardLinkBackup/pyhardlinkbackup_this_directory.sh``

Copy this file to a location that should be backed up and just call it to run a backup.

----------------------------
Verifying an existing backup
----------------------------

::

    $ cd pyhardlinkbackup/
    ~/PyHardLinkBackup $ source bin/activate
    
    (PyHardLinkBackup) ~/PyHardLinkBackup $ phlb verify --fast ~/PyHardLinkBackups/documents/2016-01-07-102310

With **--fast** the files' contents will not be checked.
If not given: The hashes from the files' contents will be calculated and compared. Thus, every file must be completely read from filesystem, so it will take some time.

A verify run does:

* Do all files in the backup exist?

* Compare file sizes

* Compare hashes from hash-file

* Compare files' modification timestamps

* Calculate hashes from files' contents and compare them (will be skipped if **--fast** used)

-------------
Configuration
-------------

phlb will use a configuration file named: **PyHardLinkBackup.ini**

Search order is:

#. current directory down to root

#. user directory

E.g. if the current working directoy is **/foo/bar/my_files/** then the search path will be:

* ``/foo/bar/my_files/PyHardLinkBackup.ini``

* ``/foo/bar/PyHardLinkBackup.ini``

* ``/foo/PyHardLinkBackup.ini``

* ``/PyHardLinkBackup.ini``

* ``~/PyHardLinkBackup.ini`` *The user home directory under Windows/Linux*

Create / edit default .ini
==========================

You can just open the editor with the user directory .ini file with:

::

    (PyHardLinkBackup) ~/PyHardLinkBackup $ phlb config

The defaults are stored here: `/phlb/config_defaults.ini <https://github.com/jedie/PyHardLinkBackup/blob/master/pyhardlinkbackup/phlb/config_defaults.ini>`_

Excluding files/folders from backup:
====================================

There are two ways to exclude files/folders from your backup.
Use the follow settings in your ``PyHardLinkBackup.ini``

::

    # Directory names that will be recursively excluded from backups (comma separated list!)
    SKIP_DIRS= __pycache__, temp
    
    # glob-style patterns to exclude files/folders from backups (used with Path.match(), Comma separated list!)
    SKIP_PATTERNS= *.pyc, *.tmp, *.cache

The filesystem scan is divided into two steps:
1. Just scan the filesystem tree
2. Filter and load meta data for every directory item

The **SKIP_DIRS** is used in the first step.
The **SKIP_PATTERNS** is used the the second step.

--------------------------
Upgrading pyhardlinkbackup
--------------------------

To upgrade to a new version just start this helper script:

* Windows: `phlb_upgrade_pyhardlinkbackup.cmd <https://github.com/jedie/PyHardLinkBackup/blob/master/pyhardlinkbackup/helper_cmd/phlb_upgrade_pyhardlinkbackup.cmd>`_

* Linux: `phlb_upgrade_pyhardlinkbackup.sh <https://github.com/jedie/PyHardLinkBackup/blob/master/pyhardlinkbackup/helper_sh/phlb_upgrade_pyhardlinkbackup.sh>`_

----------
Some notes
----------

What is 'phlb' and 'manage' ?!?
===============================

**phlb** is a CLI.

**manage** is similar to a normal Django **manage.py**, but it always
uses the pyhardlinkbackup settings.

Why in hell do you use Django?!?
================================

* Well, just because of the great database ORM and the Admin Site. ;)

How to go into the Django admin?
================================

Just start:

* Windows: ``phlb_run_django_webserver.cmd``

* Linux: ``phlb_run_django_webserver.sh``

And then request 'localhost'
(Note: **--noreload** is needed for Windows with venv!)

----------------------
Running the unit tests
----------------------

Just start: ``phlb_run_tests.cmd`` / ``phlb_run_tests.sh`` or do this:

::

    $ cd pyhardlinkbackup/
    ~/PyHardLinkBackup $ source bin/activate
    (PyHardLinkBackup) ~/PyHardLinkBackup $ manage test

-------------
Using the CLI
-------------

::

    $ cd pyhardlinkbackup/
    ~/PyHardLinkBackup $ source bin/activate
    (PyHardLinkBackup) ~/PyHardLinkBackup $ phlb --help
    Usage: phlb [OPTIONS] COMMAND [ARGS]...
    
      pyhardlinkbackup
    
    Options:
      --version  Show the version and exit.
      --help     Show this message and exit.
    
    Commands:
      add     Scan all existing backup and add missing ones...
      backup  Start a Backup run
      config  Create/edit .ini config file
      helper  link helper files to given path
      verify  Verify a existing backup

-----------------------------------
Add missing backups to the database
-----------------------------------

**phlb add** can be used in different scenarios:

* recreate the database

* add a backup manually

**phlb add** does this:

* scan the complete file tree under **BACKUP_PATH** (default: ``~/PyHardLinkBackups``)

* recreate all hash files

* add all files to database

* deduplicate with hardlinks, if possible

So it's possible to recreate the complete database:

* delete the current ``.sqlite`` file

* run **phlb add** to recreate

Another scenario is e.g.:

* DSLR images are stored on a network drive.

* You have already a copy of all files locally.

* You would like to add the local copy to pyhardlinkbackup.

Do the following steps:

* move the local files to a subdirectory below **BACKUP_PATH**

* e.g.: ``~/PyHardLinkBackups/pictures/2015-12-29-000015/``

* Note: the date format in the subdirectory name must match the **SUB_DIR_FORMATTER** in your config

* run: **phlb add**

Now you can run **phlb backup** from your network drive to make a new, up-to-date backup.

Windows Development
===================

Some notes about setting up a development environment on Windows: `/dev/WindowsDevelopment.creole <https://github.com/jedie/PyHardLinkBackup/blob/master/dev/WindowsDevelopment.creole>`_

Alternative solutions
=====================

* Attic: `https://attic-backup.org/ <https://attic-backup.org/>`_ (Not working on Windows, own backup archive format)

* BorgBackup: `https://borgbackup.readthedocs.io/ <https://borgbackup.readthedocs.io/>`_ (Fork of Attic with lots of improvements)

* msbackup: `https://pypi.python.org/pypi/msbackup/ <https://pypi.python.org/pypi/msbackup/>`_ (Uses tar for backup archives)

* Duplicity: `http://duplicity.nongnu.org/ <http://duplicity.nongnu.org/>`_ (No Windows support, tar archive format)

* Burp: `http://burp.grke.org/ <http://burp.grke.org/>`_ (Client/Server solution)

* dirvish: `http://www.dirvish.org/ <http://www.dirvish.org/>`_ (Client/Server solution)

* restic: `https://github.com/restic/restic/ <https://github.com/restic/restic/>`_ (Uses own backup archive format)

See also: `https://github.com/restic/others#list-of-backup-software <https://github.com/restic/others#list-of-backup-software>`_

-------
History
-------

* **dev** - `compare v0.12.3...master <https://github.com/jedie/PyHardLinkBackup/compare/v0.12.3...master>`_ 

    * TBC

* 17.03.2020 - v0.12.3 - `compare v0.12.2...v0.12.3 <https://github.com/jedie/PyHardLinkBackup/compare/v0.12.2...v0.12.3>`_ 

    * Fix #44 - wroing file size in process bar

    * use ``pytest-randomly``

    * update requirements

* 06.03.2020 - v0.12.2 - `compare v0.12.1...v0.12.2 <https://github.com/jedie/PyHardLinkBackup/compare/v0.12.1...v0.12.2>`_ 

    * Enhance log file content

    * Update requirements

    * `Fix too verbose output by decrease debug level <https://github.com/jedie/PyHardLinkBackup/pull/41>`_

* 05.03.2020 - v0.12.1 - `compare v0.12.0...v0.12.1 <https://github.com/jedie/PyHardLinkBackup/compare/v0.12.0...v0.12.1>`_ 

    * revert lowercase ``PyHardLinkBackup`` for environment destination and default backup directory.

* 05.03.2020 - v0.12.0 - `compare v0.11.0...v0.12.0 <https://github.com/jedie/PyHardLinkBackup/compare/v0.11.0...v0.12.0>`_ 

    * Refactor backup process: Use `https://github.com/jedie/IterFilesystem <https://github.com/jedie/IterFilesystem>`_ for less RAM usage and faster start on big source trees

    * modernized project/sources:

        * Update to Django v2.2.x TLS

        * use poetry

        * add Makefile

        * run tests with pytest and tox

        * run tests only with python 3.8, 3.7, 3.6

        * run tests on github, too

        * remove support for python 3.5 (``os.scandir`` fallback removed)

    * **NOTE:** Windows support is not tested, yet! (Help wanted)

* 03.03.2019 - v0.11.0 - `compare v0.10.1...v0.11.0 <https://github.com/jedie/PyHardLinkBackup/compare/v0.10.1...v0.11.0>`_ 

    * Update boot files

    * Use django v1.11.x

* 09.09.2016 - v0.10.1 - `compare v0.10.0...v0.10.1 <https://github.com/jedie/PyHardLinkBackup/compare/v0.10.0...v0.10.1>`_ 

    * Bugfix `Catch scan dir errors #24 <https://github.com/jedie/PyHardLinkBackup/issues/24>`_

* 26.04.2016 - v0.10.0 - `compare v0.9.1...v0.10.0 <https://github.com/jedie/PyHardLinkBackup/compare/v0.9.1...v0.10.0>`_ 

    * move under Windows the install location from ``%APPDATA%\PyHardLinkBackup`` to ``%ProgramFiles%\PyHardLinkBackup``

    * to 'migrate': Just delete ``%APPDATA%\PyHardLinkBackup`` and install via **boot_pyhardlinkbackup.cmd**

* 26.04.2016 - v0.9.1 - `compare v0.9.0...v0.9.1 <https://github.com/jedie/PyHardLinkBackup/compare/v0.9.0...v0.9.1>`_ 

    * run migrate database in boot process

    * Add missing migrate scripts

* 10.02.2016 - v0.9.0 - `compare v0.8.0...v0.9.0 <https://github.com/jedie/PyHardLinkBackup/compare/v0.8.0...v0.9.0>`_ 

    * Work-a-round for Windows MAX_PATH limit: Use ``\\?\`` path prefix internally.

    * move **Path2()** to external lib: `https://github.com/jedie/pathlib_revised <https://github.com/jedie/pathlib_revised>`_

* 04.02.2016 - v0.8.0 - `compare v0.7.0...v0.8.0 <https://github.com/jedie/PyHardLinkBackup/compare/v0.7.0...v0.8.0>`_ 

    * New: add all missing backups to database: ``phlb add`` (s.above)

* 03.02.2016 - v0.7.0 - `compare v0.6.4...v0.7.0 <https://github.com/jedie/PyHardLinkBackup/compare/v0.6.4...v0.7.0>`_ 

    * New: verify a existing backup

    * **IMPORTANT:** run database migration is needed!

* 01.02.2016 - v0.6.4 - `compare v0.6.2...v0.6.4 <https://github.com/jedie/PyHardLinkBackup/compare/v0.6.3...v0.6.4>`_ 

    * Windows: Bugfix temp rename error, because of the Windows API limitation, see: `#13 <https://github.com/jedie/PyHardLinkBackup/issues/13#issuecomment-176241894>`_

    * Linux: Bugfix scanner if symlink is broken

    * Display local variables on low level errors

* 29.01.2016 - v0.6.3 - `compare v0.6.2...v0.6.3 <https://github.com/jedie/PyHardLinkBackup/compare/v0.6.2...v0.6.3>`_ 

    * Less verbose and better information about SKIP_DIRS/SKIP_PATTERNS hits

* 28.01.2016 - v0.6.2 - `compare v0.6.1...v0.6.2 <https://github.com/jedie/PyHardLinkBackup/compare/v0.6.1...v0.6.2>`_ 

    * Handle unexpected errors and continue backup with the next file

    * Better handle interrupt key during execution

* 28.01.2016 - v0.6.1 - `compare v0.6.0...v0.6.1 <https://github.com/jedie/PyHardLinkBackup/compare/v0.6.0...v0.6.1>`_ 

    * Bugfix #13 by using a better temp rename routine

* 28.01.2016 - v0.6.0 - `compare v0.5.1...v0.6.0 <https://github.com/jedie/PyHardLinkBackup/compare/v0.5.1...v0.6.0>`_ 

    * New: faster backup by compare mtime/size only if old backup files exists

* 27.01.2016 - v0.5.1 - `compare v0.5.0...v0.5.1 <https://github.com/jedie/PyHardLinkBackup/compare/v0.5.0...v0.5.1>`_ 

    * **IMPORTANT:** run database migration is needed!

    * New ``.ini`` setting: ``LANGUAGE_CODE`` for change translation

    * mark if backup was finished compled

    * Display information of last backup run

    * Add more information into summary file

* 27.01.2016 - v0.5.0 - `compare v0.4.2...v0.5.0 <https://github.com/jedie/PyHardLinkBackup/compare/v0.4.2...v0.5.0>`_ 

    * refactory source tree scan. Split in two passed.

    * **CHANGE** ``SKIP_FILES`` in ``.ini`` config to: ``SKIP_PATTERNS``

    * Backup from newest files to oldest files.

    * Fix `#10 <https://github.com/jedie/PyHardLinkBackup/issues/10>`_:

        * New **--name** cli option (optional) to force a backup name.

        * Display error message if backup name can be found (e.g.: backup a root folder)

* 22.01.2016 - v0.4.2 - `compare v0.4.1...v0.4.2 <https://github.com/jedie/PyHardLinkBackup/compare/v0.4.1...v0.4.2>`_ 

    * work-a-round for junction under windows, see also: `https://www.python-forum.de/viewtopic.php?f=1&t=37725&p=290429#p290428 <https://www.python-forum.de/viewtopic.php?f=1&t=37725&p=290429#p290428>`_ (de)

    * Bugfix in windows batches: go into work dir.

    * print some more status information in between.

* 22.01.2016 - v0.4.1 - `compare v0.4.0...v0.4.1 <https://github.com/jedie/PyHardLinkBackup/compare/v0.4.0...v0.4.1>`_ 

    * Skip files that can't be read/write. (and try to backup the remaining files)

* 21.01.2016 - v0.4.0 - `compare v0.3.1...v0.4.0 <https://github.com/jedie/PyHardLinkBackup/compare/v0.3.1...v0.4.0>`_ 

    * Search for *PyHardLinkBackup.ini* file in every parent directory from the current working dir

    * increase default chunk size to 20MB

    * save summary and log file for every backup run

* 15.01.2016 - v0.3.1 - `compare v0.3.0...v0.3.1 <https://github.com/jedie/PyHardLinkBackup/compare/v0.3.0...v0.3.1>`_ 

    * fix unittest run under windows

* 15.01.2016 - v0.3.0 - `compare v0.2.0...v0.3.0 <https://github.com/jedie/PyHardLinkBackup/compare/v0.2.0...v0.3.0>`_ 

    * **database migration needed**

    * Add 'no_link_source' to database (e.g. Skip source, if 1024 links created under windows)

* 14.01.2016 - v0.2.0 - `compare v0.1.8...v0.2.0 <https://github.com/jedie/PyHardLinkBackup/compare/v0.1.8...v0.2.0>`_ 

    * good unittests coverage that covers the backup process

* 08.01.2016 - v0.1.8 - `compare v0.1.0alpha0...v0.1.8 <https://github.com/jedie/PyHardLinkBackup/compare/v0.1.0alpha0...v0.1.8>`_ 

    * install and runable under Windows

* 06.01.2016 - v0.1.0alpha0 - `d42a5c5 <https://github.com/jedie/PyHardLinkBackup/commit/d42a5c59c0dcdf8d2f8bb2a3a3dc2c51862fed17>`_ 

    * first Release on PyPi

* 29.12.2015 - `commit 2ce43 <https://github.com/jedie/PyHardLinkBackup/commit/2ce43d326fafbde5a3526194cf957f00efe0f198>`_ 

    * commit 'Proof of concept'

-----
Links
-----

* `https://pypi.python.org/pypi/pyhardlinkbackup/ <https://pypi.python.org/pypi/pyhardlinkbackup/>`_

* `https://www.python-forum.de/viewtopic.php?f=6&t=37723 <https://www.python-forum.de/viewtopic.php?f=6&t=37723>`_ (de)

* `https://github.com/jedie/pathlib_revised`_

--------
Donating
--------

* `paypal.me/JensDiemer <https://www.paypal.me/JensDiemer>`_

* `Flattr This! <https://flattr.com/submit/auto?uid=jedie&url=https%3A%2F%2Fgithub.com%2Fjedie%2Fdjango-reversion-compare%2F>`_

* Send `Bitcoins <http://www.bitcoin.org/>`_ to `1823RZ5Md1Q2X5aSXRC5LRPcYdveCiVX6F <https://blockexplorer.com/address/1823RZ5Md1Q2X5aSXRC5LRPcYdveCiVX6F>`_

------------

``Note: this file is generated from README.creole 2020-03-17 09:38:29 with "python-creole"``