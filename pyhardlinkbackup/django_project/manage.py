#!/usr/bin/env python3

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pyhardlinkbackup.django_project.settings")


def cli():
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    # Needed if direct called
    cli()
