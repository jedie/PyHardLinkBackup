#!/usr/bin/env python3

"""
    pyhardlinkbackup cli using click
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""


import os
import sys

import click
import django
from django.core import management

# https://github.com/jedie/PyHardLinkBackup
import pyhardlinkbackup
from pyhardlinkbackup.phlb.config import phlb_config

PHLB_BASE_DIR = os.path.abspath(os.path.dirname(pyhardlinkbackup.__file__))


@click.group()
@click.version_option(version=pyhardlinkbackup.__version__)
@click.pass_context
def cli(ctx):
    """pyhardlinkbackup"""
    click.secho(
        f"\npyhardlinkbackup v{pyhardlinkbackup.__version__}\n",
        bg="blue",
        fg="white",
        bold=True)


@cli.command()
@click.argument(
    "path",
    type=click.Path(
        exists=True,
        file_okay=False,
        dir_okay=True,
        writable=True,
        resolve_path=True))
def helper(path):
    """
    link helper files to given path
    """
    if sys.platform.startswith("win"):
        # link batch files
        src_path = os.path.join(PHLB_BASE_DIR, "helper_cmd")
    elif sys.platform.startswith("linux"):
        # link shell scripts
        src_path = os.path.join(PHLB_BASE_DIR, "helper_sh")
    else:
        print(f"TODO: {sys.platform}")
        return

    if not os.path.isdir(src_path):
        raise RuntimeError(f"Helper script path not found here: '{src_path}'")

    for entry in os.scandir(src_path):
        print("_" * 79)
        print(f"Link file: '{entry.name}'")
        src = entry.path
        dst = os.path.join(path, entry.name)
        if os.path.exists(dst):
            print(f"Remove old file '{dst}'")
            try:
                os.remove(dst)
            except OSError as err:
                print(f"\nERROR:\n{err}\n")
                continue

        print(f"source.....: '{src}'")
        print(f"destination: '{dst}'")
        try:
            os.link(src, dst)
        except OSError as err:
            print(f"\nERROR:\n{err}\n")
            continue


cli.add_command(helper)


@click.command()
@click.option("--debug", is_flag=True, default=False, help="Display used config and exit.")
def config(debug):
    """Create/edit .ini config file"""
    if debug:
        phlb_config.print_config()
    else:
        phlb_config.open_editor()


cli.add_command(config)


@click.command()
@click.argument(
    "path",
    type=click.Path(
        exists=True,
        file_okay=False,
        dir_okay=True,
        writable=False,
        readable=True,
        resolve_path=True),
)
@click.option("--name", help="Force a backup name (If not set: Use parent directory name)")
def backup(path, name=None):
    """Start a Backup run"""
    django.setup()
    from pyhardlinkbackup.phlb.main import backup
    backup(path, name)
    print('Backup done.')


cli.add_command(backup)


@click.command()
@click.argument(
    "backup_path",
    type=click.Path(
        exists=True,
        file_okay=False,
        dir_okay=True,
        writable=False,
        readable=True,
        resolve_path=True),
)
@click.option("--fast", is_flag=True, default=False,
              help="Don't compare real file content (Skip calculate hash)")
def verify(backup_path, fast):
    """Verify a existing backup"""
    django.setup()
    from pyhardlinkbackup.phlb.verify import verify_backup
    verify_backup(backup_path, fast)


cli.add_command(verify)


@click.command()
def add():
    """Scan all existing backup and add missing ones to database."""
    django.setup()
    from pyhardlinkbackup.backup_app.management.commands import add
    management.call_command(add.Command())


cli.add_command(add)


if __name__ == "__main__":
    cli()
