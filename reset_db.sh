#!/bin/bash

if [ ! -n "$VIRTUAL_ENV" ] ; then
    echo "ERROR: Please activate virtualenv first!"
    exit -1
fi

set -x
set -e

cd PyHardLinkBackup
rm db.sqlite3

rm backup_app/migrations/0*.py
./manage.py makemigrations

./manage.py syncdb --noinput
./manage.py migrate --noinput
./manage.py createsuperuser --username=test --email=
