#!/usr/bin/env bash

ENV_PATH=~/pyhardlinkbackup
CURRENT_DIR=$(pwd)

set -e

ACTIVATE_SCRIPT=${ENV_PATH}/bin/activate
echo "Activate venv with: ${ACTIVATE_SCRIPT}"
source ${ACTIVATE_SCRIPT}

set -x

manage migrate
