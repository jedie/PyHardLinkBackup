#!/bin/bash

if [ ! -n "$VIRTUAL_ENV" ] ; then
    echo "ERROR: Please activate virtualenv first!"
    exit -1
fi

set -x

rm ~/PyHardLinkBackups.sqlite3

cd PyHardLinkBackup
rm backup_app/migrations/0*.py

set -e

phlb makemigrations

phlb migrate --noinput

phlb runserver
