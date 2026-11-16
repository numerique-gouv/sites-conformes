#!/bin/bash

# Perform a backup of the local database and medias

# Manage environment variables
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

set -a
[ -f  ${SCRIPT_DIR}/../.env ] && . ${SCRIPT_DIR}/../.env && echo "Local env variables loaded"
set +a

if [[ -z "$BACKUP_DIR" ]]; then
    echo "Please set BACKUP_DIR to a directory outsite of the django path" 1>&2
    exit 1
fi

echo "Backuping ${APP_NAME} as `whoami`"

# Create the backup directory if it doesn't exist
test -d ${BACKUP_DIR} || mkdir -p ${BACKUP_DIR}

# Run the backups
DATE=`date '+%Y%m%d-%H%M'`

echo "${DATE}"

echo "SQL dump"
pg_dump --no-privileges --no-owner -U ${DATABASE_USER} -h ${DATABASE_HOST} -p ${DATABASE_PORT} -d ${DATABASE_NAME} -F c -Z 9 -f ${BACKUP_DIR}/sites-conformes-local-db-${DATE}.sql.gz

echo "Medias backup"
cd ${SCRIPT_DIR}/../
tar cvzf ${BACKUP_DIR}/sites-conformes-local-medias-${DATE}.tar.gz ${MEDIA_ROOT:=medias}/

echo "New backup files:"
ls -hal ${BACKUP_DIR}/*${DATE}*
