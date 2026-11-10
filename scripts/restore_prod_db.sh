#!/bin/bash

# Restore the latest downloaded backup of the production database

# Manage environment variables
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
export PGPASSWORD=${DATABASE_PASSWORD}

set -a
[ -f  ${SCRIPT_DIR}/../.env ] && . ${SCRIPT_DIR}/../.env && echo "Local env variables loaded"
set +a

if [[ -z "$BACKUP_DIR" ]]; then
    echo "Please set BACKUP_DIR to a directory outsite of the django path" 1>&2
    exit 1
fi

if [[ -z "$PROD_APP" ]]; then
    echo "Please set PROD_APP" 1>&2
    exit 1
fi

# NAME=value lines from `scalingo --app "$PROD_APP" env`. Values may contain "=".
scalingo_env="$(scalingo --app "${PROD_APP}" env)" || exit 1

# Print the value of one Scalingo variable. Return 1 when it is absent.
scalingo_var() {
    local line
    line="$(printf '%s\n' "$scalingo_env" | grep -m 1 "^${1}=")" || return 1
    printf '%s' "${line#*=}"
}

# Print the value. Return 1 when the variable is absent or empty.
require_scalingo_var() {
    local value
    if ! value="$(scalingo_var "$1")" || [[ -z "$value" ]]; then
        echo "Missing ${1} in Scalingo env for ${PROD_APP}" >&2
        return 1
    fi
    printf '%s' "$value"
}

database_url="$(require_scalingo_var SCALINGO_POSTGRESQL_URL)" || exit 1
PROD_DB_NAME="${database_url%%\?*}"
PROD_DB_NAME="${PROD_DB_NAME##*/}"
unset database_url
if [[ -z "$PROD_DB_NAME" ]]; then
    echo "Could not read the database name from SCALINGO_POSTGRESQL_URL" >&2
    exit 1
fi
export PROD_DB_NAME

cd ${BACKUP_DIR}

TAR_FILE=`ls *_${PROD_DB_NAME}.tar.gz -c | head -1`
tar xzf ${TAR_FILE}

BACKUP_FILE=`ls *_${PROD_DB_NAME}.pgsql -c | head -1`

echo "Restoring database ${DATABASE_NAME} with backup ${BACKUP_FILE}"

dropdb -U ${DATABASE_USER} -h ${DATABASE_HOST} -p ${DATABASE_PORT} ${DATABASE_NAME} --force --if-exists

psql -d postgres -c "CREATE DATABASE ${DATABASE_NAME} OWNER ${DATABASE_USER};" -U ${DATABASE_USER} -h ${DATABASE_HOST} -p ${DATABASE_PORT}

pg_restore --clean --if-exists --no-owner --no-privileges --no-comments --role=${DATABASE_USER} -d ${DATABASE_NAME} ${BACKUP_FILE} -U ${DATABASE_USER} -h ${DATABASE_HOST} -p ${DATABASE_PORT}

psql -d ${DATABASE_NAME} -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DATABASE_USER}; GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${DATABASE_USER}; GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO ${DATABASE_USER};" -U ${DATABASE_USER} -h ${DATABASE_HOST} -p ${DATABASE_PORT}
