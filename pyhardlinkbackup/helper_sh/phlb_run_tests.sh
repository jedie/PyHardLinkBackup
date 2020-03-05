#!/usr/bin/env bash

ENV_PATH=~/PyHardLinkBackup
CURRENT_DIR=$(pwd)

set -e

ACTIVATE_SCRIPT=${ENV_PATH}/bin/activate
echo "Activate venv with: ${ACTIVATE_SCRIPT}"
source ${ACTIVATE_SCRIPT}

PKG_PATH=$(python -c "import os,pyhardlinkbackup;print(os.path.dirname(pyhardlinkbackup.__file__))")
echo PKG_PATH: ${PKG_PATH}

cd ${PKG_PATH}
(
    set -x
    pip3 install --upgrade pip
    pip3 install -r requirements/dev_extras.txt
    coverage run --source=pyhardlinkbackup --parallel-mode -m pyhardlinkbackup.django_project.manage test pyhardlinkbackup --verbosity=2
)

if [ "${1}" != "no_report" ]; then
    # not called from Travis CI
    (
        set -x
        coverage combine
        coverage html
        python3 -m webbrowser -t "htmlcov/index.html"
    )
fi


