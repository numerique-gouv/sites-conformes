#!/bin/bash

# Restore the latest backup from the local database

# Manage environment variables
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

set -a
[ -f  ${SCRIPT_DIR}/../.env ] && . ${SCRIPT_DIR}/../.env && echo "Local env variables loaded"
set +a

if [[ -z "$BACKUP_DIR" ]]; then
    echo "Please set BACKUP_DIR to a directory outsite of the django path" 1>&2
    exit 1
fi

cd ${BACKUP_DIR}

BACKUP_FILE=`ls sites-conformes-local-db-*.sql.gz -c | head -1`

echo "Restoring database ${DATABASE_NAME} with backup ${BACKUP_FILE}"

dropdb -U ${DATABASE_USER} -h ${DATABASE_HOST} -p ${DATABASE_PORT} ${DATABASE_NAME} --force --if-exists
psql -c "CREATE DATABASE ${DATABASE_NAME} OWNER ${DATABASE_USER};" -U postgres

pg_restore --clean --if-exists --no-owner --no-privileges --no-comments --role=${DATABASE_USER} -d ${DATABASE_NAME} ${BACKUP_FILE} -U ${DATABASE_USER} -h ${DATABASE_HOST} -p ${DATABASE_PORT}
psql -d ${DATABASE_NAME} -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DATABASE_USER}; GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${DATABASE_USER}; GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO ${DATABASE_USER};" -U ${DATABASE_USER} -h ${DATABASE_HOST} -p ${DATABASE_PORT}
