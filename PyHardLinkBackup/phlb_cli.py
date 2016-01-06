#!/usr/bin/env python3

"""
    Main entry point for PyHardLinkBackup
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This is just a django "manage.py" that will always used
    the own settings.

    https://docs.djangoproject.com/en/1.8/ref/django-admin/
"""


import os
import sys


def cli():
    os.environ["DJANGO_SETTINGS_MODULE"] = "PyHardLinkBackup.django_project.settings"
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    cli()

