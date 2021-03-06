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
        wget --timestamp https://bootstrap.pypa.io/get-pip.py
        ${DESTINATION}/bin/python get-pip.py
        rm get-pip.py
    )
fi
(
    set -e
    source ${DESTINATION}/bin/activate
    set -x
    cd ${DESTINATION}/bin/
    ls -la
    pip3 install --upgrade pip
    pip3 install "pyhardlinkbackup>=0.12.1"
    phlb helper ${DESTINATION}
    manage migrate
)
