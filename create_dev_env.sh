#!/usr/bin/env bash

BASE_DIR=$(pwd)
DESTINATION=${BASE_DIR}/.virtualenv
REQ_FILE=

(
    set -e
    set -x

    python3 --version
    python3 -Im venv --without-pip ${DESTINATION}
)
(
    source ${DESTINATION}/bin/activate
    set -x
    python3 -m ensurepip
)
if [ "$?" == "0" ]; then
    echo "pip installed, ok"
else
    echo "ensurepip doesn't exist, use get-pip.py"
    (
        set -e
        source ${DESTINATION}/bin/activate
        set -x
        cd ${DESTINATION}/bin
        wget https://bootstrap.pypa.io/get-pip.py
        ${DESTINATION}/bin/python get-pip.py
    )
fi
(
    set -e
    source ${DESTINATION}/bin/activate
    set -x

    pip3 install --upgrade pip
    pip3 install \
        -r ${BASE_DIR}/PyHardLinkBackup/requirements/normal_installation.txt \
        -r ${BASE_DIR}/PyHardLinkBackup/requirements/dev_extras.txt

    cd ${BASE_DIR}
    pip3 install -e .
)
