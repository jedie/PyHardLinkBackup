"""
    pyhardlinkbackup django manage
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    usage e.g.:

        ~/PyHardLinkBackup$ poetry run manage --help
"""


import sys

import django

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup import __version__
from pyhardlinkbackup.phlb.traceback_plus import print_exc_plus


def cli():
    print(f'PyHardLinkBackup v{__version__} - Django v{django.__version__} manage command')

    from django.core.management import execute_from_command_line

    try:
        execute_from_command_line(sys.argv)
    except SystemExit as err:
        sys.exit(err.code)
    except BaseException:
        print_exc_plus()
        raise


if __name__ == "__main__":
    import warnings
    warnings.warn('Do not call this file directly! Use "poetry run manage --help" !')
    cli()
