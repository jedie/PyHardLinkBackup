#!/usr/bin/env python
# coding: utf-8

"""
    pathlib revised distutils setup
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Links
    ~~~~~

    http://www.python-forum.de/viewtopic.php?f=21&t=26895 (de)

    :copyleft: 2016 by the pathlib revised team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""

from __future__ import absolute_import, division, print_function


import os
import shutil
import subprocess
import sys

from setuptools import setup, find_packages

from PyHardLinkBackup import __version__


PACKAGE_ROOT = os.path.dirname(os.path.abspath(__file__))


# _____________________________________________________________________________
# convert creole to ReSt on-the-fly, see also:
# https://github.com/jedie/python-creole/wiki/Use-In-Setup
long_description = None
for arg in ("test", "check", "register", "sdist", "--long-description"):
    if arg in sys.argv:
        try:
            from creole.setup_utils import get_long_description
        except ImportError as err:
            raise ImportError("%s - Please install python-creole - e.g.: pip install python-creole" % err)
        else:
            long_description = get_long_description(PACKAGE_ROOT)
        break
# ----------------------------------------------------------------------------

if "publish" in sys.argv:
    """
    'publish' helper for setup.py

    Build and upload to PyPi, if...
        ... __version__ doesn't contains "dev"
        ... we are on git 'master' branch
        ... git repository is 'clean' (no changed files)

    Upload with "twine", git tag the current version and git push --tag

    The cli arguments will be pass to 'twine'. So this is possible:
     * Display 'twine' help page...: ./setup.py publish --help
     * use testpypi................: ./setup.py publish --repository=test

    TODO: Look at: https://github.com/zestsoftware/zest.releaser

    Source: https://github.com/jedie/python-code-snippets/blob/master/CodeSnippets/setup_publish.py
    copyleft 2015-2019 Jens Diemer - GNU GPL v2+
    """
    assert sys.version_info[0] > 2, "Python v3 is needed!"

    import_error = False
    try:
        # Test if wheel is installed, otherwise the user will only see:
        #   error: invalid command 'bdist_wheel'
        import wheel
    except ImportError as err:
        print("\nError: %s" % err)
        print("\nMaybe https://pypi.org/project/wheel is not installed or virtualenv not activated?!?")
        print("e.g.:")
        print("    ~/your/env/$ source bin/activate")
        print("    ~/your/env/$ pip install wheel")
        import_error = True

    try:
        import twine
    except ImportError as err:
        print("\nError: %s" % err)
        print("\nMaybe https://pypi.org/project/twine is not installed or virtualenv not activated?!?")
        print("e.g.:")
        print("    ~/your/env/$ source bin/activate")
        print("    ~/your/env/$ pip install twine")
        import_error = True

    if import_error:
        sys.exit(-1)

    def verbose_check_output(*args):
        """ 'verbose' version of subprocess.check_output() """
        call_info = "Call: %r" % " ".join(args)
        try:
            output = subprocess.check_output(args, universal_newlines=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as err:
            print("\n***ERROR:")
            print(err.output)
            raise
        return call_info, output

    def verbose_check_call(*args):
        """ 'verbose' version of subprocess.check_call() """
        print("\tCall: %r\n" % " ".join(args))
        subprocess.check_call(args, universal_newlines=True)

    def confirm(txt):
        print("\n%s" % txt)
        if input("\nPublish anyhow? (Y/N)").lower() not in ("y", "j"):
            print("Bye.")
            sys.exit(-1)

    for key in ("dev", "rc"):
        if key in __version__:
            confirm("WARNING: Version contains %r: v%s\n" % (key, __version__))
            break

    print("\nCheck if we are on 'master' branch:")
    call_info, output = verbose_check_output("git", "branch", "--no-color")
    print("\t%s" % call_info)
    if "* master" in output:
        print("OK")
    else:
        confirm("\nNOTE: It seems you are not on 'master':\n%s" % output)

    print("\ncheck if if git repro is clean:")
    call_info, output = verbose_check_output("git", "status", "--porcelain")
    print("\t%s" % call_info)
    if output == "":
        print("OK")
    else:
        print("\n *** ERROR: git repro not clean:")
        print(output)
        sys.exit(-1)

    print("\nRun './setup.py check':")
    call_info, output = verbose_check_output("./setup.py", "check")
    if "warning" in output:
        print(output)
        confirm("Warning found!")
    else:
        print("OK")

    print("\ncheck if pull is needed")
    verbose_check_call("git", "fetch", "--all")
    call_info, output = verbose_check_output("git", "log", "HEAD..origin/master", "--oneline")
    print("\t%s" % call_info)
    if output == "":
        print("OK")
    else:
        print("\n *** ERROR: git repro is not up-to-date:")
        print(output)
        sys.exit(-1)
    verbose_check_call("git", "push")

    print("\nCleanup old builds:")

    def rmtree(path):
        path = os.path.abspath(path)
        if os.path.isdir(path):
            print("\tremove tree:", path)
            shutil.rmtree(path)

    rmtree("./dist")
    rmtree("./build")

    print("\nbuild but don't upload...")
    log_filename = "build.log"
    with open(log_filename, "a") as log:
        call_info, output = verbose_check_output(
            sys.executable or "python", "setup.py", "sdist", "bdist_wheel", "bdist_egg"
        )
        print("\t%s" % call_info)
        log.write(call_info)
        log.write(output)
    print("Build output is in log file: %r" % log_filename)

    git_tag = "v%s" % __version__

    print("\ncheck git tag")
    call_info, output = verbose_check_output("git", "log", "HEAD..origin/master", "--oneline")
    if git_tag in output:
        print("\n *** ERROR: git tag %r already exists!" % git_tag)
        print(output)
        sys.exit(-1)
    else:
        print("OK")

    print("\nUpload with twine:")
    twine_args = sys.argv[1:]
    twine_args.remove("publish")
    twine_args.insert(1, "dist/*")
    print("\ttwine upload command args: %r" % " ".join(twine_args))
    from twine.commands.upload import main as twine_upload

    twine_upload(twine_args)

    print("\ngit tag version")
    verbose_check_call("git", "tag", git_tag)

    print("\ngit push tag to server")
    verbose_check_call("git", "push", "--tags")

    sys.exit(0)



def get_authors():
    try:
        with open(os.path.join(PACKAGE_ROOT, "AUTHORS"), "r") as f:
            authors = [l.strip(" *\r\n") for l in f if l.strip().startswith("*")]
    except Exception as err:
        authors = "[Error: %s]" % err
    return authors


setup(
    name='PyHardLinkBackup',
    version=__version__,
    description='HardLink/Deduplication Backups with Python',
    long_description=long_description,
    keywords="Backup Hardlink Windows Linux",
    license = "GNU General Public License (GNU GPL v3 or above)",
    author=get_authors(),
    author_email="pypi@jensdiemer.de",
    maintainer="Jens Diemer",
    maintainer_email="pypi@jensdiemer.de",
    url='https://github.com/jedie/PyHardLinkBackup',
    packages=find_packages(),
    include_package_data=True, # include package data under version control
    install_requires=[
        "pathlib_revised", # https://github.com/jedie/pathlib_revised/
        #
        # https://www.djangoproject.com/download/#supported-versions
        # v1.11 LTS - extended support until April 2020
        "django>=1.11,<2.0",
        "django-tools", # https://github.com/jedie/django-tools/
        "tqdm", # https://github.com/tqdm/tqdm
        "click", # https://github.com/mitsuhiko/click
    ],
    extras_require={
        ':python_version=="3.3" or python_version=="3.4"': [
            "scandir", # https://pypi.python.org/pypi/scandir
        ],
    },
    entry_points={'console_scripts': [
        'phlb = PyHardLinkBackup.phlb_cli:cli',
        'manage = PyHardLinkBackup.django_project.manage:cli',
    ]},
    zip_safe=False,
    classifiers=[
        "Development Status :: 4 - Beta",
       #  "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3 :: Only",
        'Framework :: Django',
        "Topic :: Database :: Front-Ends",
        "Topic :: Documentation",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Internet :: WWW/HTTP :: Site Management",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        "Operating System :: OS Independent",
    ],
    # test_suite="runtests.cli_run",
)
