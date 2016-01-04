#!/usr/bin/env python3


import os
import sys


def cli():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "PyHardLinkBackup.django_project.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    cli()

