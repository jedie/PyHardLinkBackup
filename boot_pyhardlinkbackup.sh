#!/usr/bin/env bash

DESTINATION=~/PyHardLinkBackup

(
    set -e
    set -x

    python3 --version

    python3 -Im venv --without-pip ${DESTINATION}

    ls -la ${DESTINATION}/bin
)
(
    set -x
    ${DESTINATION}/bin/python -m ensurepip
)
if [ "$?" == "0" ]; then
    echo "pip installed, ok"
else
    echo "ensurepip doesn't exist, use get-pip.py"
    (
        set -e
        set -x
        cd ${DESTINATION}/bin
        wget https://bootstrap.pypa.io/get-pip.py
        ${DESTINATION}/bin/python get-pip.py
    )
fi
source ${DESTINATION}/bin/activate
(
    set -e
    set -x
    pip install --upgrade pip

    pip install PyHardLinkBackup

    phlb_setup_helper_files
)