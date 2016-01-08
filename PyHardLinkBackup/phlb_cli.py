#!/usr/bin/env python3

"""
    Main entry point for PyHardLinkBackup
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



    https://docs.djangoproject.com/en/1.8/ref/django-admin/
"""


import os
import sys


# Use the built-in version of scandir/walk if possible, otherwise
# use the scandir module version
try:
    from os import scandir # new in Python 3.5
except ImportError:
    # use https://pypi.python.org/pypi/scandir
    try:
        from scandir import scandir
    except ImportError:
        raise ImportError("For Python <2.5: Please install 'scandir' !")


import PyHardLinkBackup


def setup_helper_files():
    """
    put helper files in venv root dir
    """
    BASE_DIR=os.path.abspath(os.path.dirname(PyHardLinkBackup.__file__))

    ENV_ROOT=os.path.normpath(os.path.join(os.path.dirname(sys.argv[0]), ".."))
    if not os.path.isdir(ENV_ROOT):
        raise RuntimeError("venv not found here: %r" % ENV_ROOT)

    if sys.platform.startswith("win"):
        # link batch files
        src_path = os.path.join(BASE_DIR, "helper_cmd")
    else:
        print("TODO!")
        return

    if not os.path.isdir(src_path):
        raise RuntimeError("Helper script path not found here: %r" % src_path)

    for entry in scandir(src_path):
        print("_"*79)
        print("Update file: %r" % entry.name)
        src = entry.path
        dst = os.path.join(ENV_ROOT, entry.name)
        if os.path.exists(dst):
            print("Remove old file %r" % dst)
            try:
                os.remove(dst)
            except OSError as err:
                print("\nERROR:\n%s\n" % err)
                continue

        print("source.....: %r" % src)
        print("destination: %r" % dst)
        try:
            os.link(src, dst)
        except OSError as err:
            print("\nERROR:\n%s\n" % err)
            continue


def manage():
    """
    This is just a django "manage.py" that will always used
    the own settings.
    """
    os.environ["DJANGO_SETTINGS_MODULE"] = "PyHardLinkBackup.django_project.settings"
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    manage()

