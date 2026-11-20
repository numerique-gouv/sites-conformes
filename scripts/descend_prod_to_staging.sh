#!/bin/bash

# Copy the database and the media files of the production app to the staging app
#
# Usage: descend_prod_to_staging.sh [--db-only | --medias-only]
#
# The database comes from the latest Scalingo backup of the production app, so that the
# production database is not loaded. The media files are synchronized from the production
# S3 bucket to the staging one. The secrets of both apps are read from their Scalingo env.
#
# PROD_REGION defaults to osc-fr1, STAGING_REGION defaults to PROD_REGION.
#
# Production must run PostgreSQL 15 or newer and staging PostgreSQL 18 or newer. Staging must not
# be older than production, and the local pg_restore must be able to read the dump without being
# newer than the staging server. These checks run before anything is modified.

# Manage environment variables
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

set -a
[ -f  ${SCRIPT_DIR}/../.env ] && . ${SCRIPT_DIR}/../.env && echo "Local env variables loaded"
set +a

set -euo pipefail

usage() {
    echo "Usage: $0 [--db-only | --medias-only]" 1>&2
    exit 1
}

DO_DB=1
DO_MEDIAS=1
for arg in "$@"; do
    case "$arg" in
        --db-only)
            DO_MEDIAS=0
            ;;
        --medias-only)
            DO_DB=0
            ;;
        *)
            usage
            ;;
    esac
done
if [[ $DO_DB -eq 0 && $DO_MEDIAS -eq 0 ]]; then
    echo "--db-only and --medias-only cannot be used together" 1>&2
    usage
fi

if [[ -z "${PROD_APP:-}" ]]; then
    echo "Please set PROD_APP" 1>&2
    exit 1
fi

if [[ -z "${STAGING_APP:-}" ]]; then
    echo "Please set STAGING_APP" 1>&2
    exit 1
fi

if [[ "$PROD_APP" == "$STAGING_APP" ]]; then
    echo "PROD_APP and STAGING_APP are both set to ${PROD_APP}, aborting" 1>&2
    exit 1
fi

# The backup directory only holds the database dump
if [[ $DO_DB -eq 1 && -z "${BACKUP_DIR:-}" ]]; then
    echo "Please set BACKUP_DIR to a directory outsite of the django path" 1>&2
    exit 1
fi

PROD_REGION=${PROD_REGION:-osc-fr1}
STAGING_REGION=${STAGING_REGION:-$PROD_REGION}
TUNNEL_PORT=${TUNNEL_PORT:-10000}
# Seconds to wait for each attempt: the CLI can take about 30s to get its access token
TUNNEL_TIMEOUT=${TUNNEL_TIMEOUT:-60}
SC_RETRIES=${SC_RETRIES:-3}
# Minimum PostgreSQL major versions of the source and destination databases.
# A dump of an older server can be restored to a newer one, not the other way round.
MIN_PROD_PG_VERSION=15
MIN_STAGING_PG_VERSION=18

REQUIRED_COMMANDS="scalingo"
if [[ $DO_DB -eq 1 ]]; then
    REQUIRED_COMMANDS="${REQUIRED_COMMANDS} pg_restore psql"
fi
if [[ $DO_MEDIAS -eq 1 ]]; then
    REQUIRED_COMMANDS="${REQUIRED_COMMANDS} rclone"
fi
for cmd in ${REQUIRED_COMMANDS}; do
    if ! command -v $cmd &> /dev/null; then
        echo "Missing command: ${cmd}" 1>&2
        exit 1
    fi
done

# Run a Scalingo command: sc_retry REGION APP ARGS...
# The Scalingo API sometimes times out: only use it for commands that can safely be run twice
sc_retry() {
    local region=$1 app=$2
    shift 2
    local attempt
    local output_file
    output_file=`mktemp`
    for attempt in $(seq 1 ${SC_RETRIES}); do
        if [[ -t 1 ]]; then
            # Keep the terminal as stdout so that the CLI can display its progress bars
            if scalingo --region ${region} --app ${app} "$@"; then
                rm -f ${output_file}
                return 0
            fi
        else
            # The CLI writes its errors on stdout: only pass on the output of the attempt that
            # succeeds, so that the errors end up on stderr instead of in the captured output
            if scalingo --region ${region} --app ${app} "$@" > ${output_file}; then
                cat ${output_file}
                rm -f ${output_file}
                return 0
            fi
            cat ${output_file} 1>&2
        fi
        if [[ $attempt -lt ${SC_RETRIES} ]]; then
            echo "Scalingo command failed (attempt ${attempt}/${SC_RETRIES}), retrying in $((attempt * 5))s: $*" 1>&2
            sleep $((attempt * 5))
        fi
    done
    rm -f ${output_file}
    echo "Scalingo command failed after ${SC_RETRIES} attempts on ${app}: $*" 1>&2
    return 1
}

# NAME=value lines from `scalingo env`. Values may contain "=".
echo "Reading the Scalingo env of ${PROD_APP} and ${STAGING_APP}"
prod_env="$(sc_retry ${PROD_REGION} ${PROD_APP} env)"
staging_env="$(sc_retry ${STAGING_REGION} ${STAGING_APP} env)"

# Print the value of one variable of an env: scalingo_var ENV NAME. Return 1 when it is absent.
scalingo_var() {
    local line
    line="$(printf '%s\n' "$1" | grep -m 1 "^${2}=")" || return 1
    printf '%s' "${line#*=}"
}

# Print the value: require_scalingo_var ENV APP NAME. Return 1 when it is absent or empty.
require_scalingo_var() {
    local value
    if ! value="$(scalingo_var "$1" "$3")" || [[ -z "$value" ]]; then
        echo "Missing ${3} in Scalingo env for ${2}" >&2
        return 1
    fi
    printf '%s' "$value"
}

#### Checks (nothing is modified until the confirmation)

# Configure an rclone remote from the S3 settings of an app: configure_s3_remote REMOTE ENV APP
# Sets ${REMOTE}_S3_PATH to the bucket and location of the app.
configure_s3_remote() {
    local remote=$1 env=$2 app=$3
    local bucket location host protocol region key_id key_secret
    bucket="$(require_scalingo_var "$env" $app S3_BUCKET_NAME)" || exit 1
    # Absent or empty S3_LOCATION means the bucket root.
    location="$(scalingo_var "$env" S3_LOCATION || true)"
    host="$(require_scalingo_var "$env" $app S3_HOST)" || exit 1
    protocol="$(scalingo_var "$env" S3_PROTOCOL || true)"
    region="$(require_scalingo_var "$env" $app S3_BUCKET_REGION)" || exit 1
    key_id="$(require_scalingo_var "$env" $app S3_KEY_ID)" || exit 1
    key_secret="$(require_scalingo_var "$env" $app S3_KEY_SECRET)" || exit 1
    # rclone reads the remotes from RCLONE_CONFIG_<NAME>_* (used as "<name>:" on the command line)
    export RCLONE_CONFIG_${remote}_TYPE=s3
    export RCLONE_CONFIG_${remote}_PROVIDER=Other
    export RCLONE_CONFIG_${remote}_ENDPOINT="${protocol:-https}://${host}"
    export RCLONE_CONFIG_${remote}_REGION="${region}"
    export RCLONE_CONFIG_${remote}_ACCESS_KEY_ID="${key_id}"
    export RCLONE_CONFIG_${remote}_SECRET_ACCESS_KEY="${key_secret}"
    printf -v ${remote}_S3_PATH '%s' "${bucket}/${location}"
}

check_medias() {
    configure_s3_remote PROD "$prod_env" ${PROD_APP}
    configure_s3_remote STAGING "$staging_env" ${STAGING_APP}

    # Compare the paths without trailing slashes: "bucket/" and "bucket" are the same place
    if [[ "${PROD_S3_PATH%/}" == "${STAGING_S3_PATH%/}" \
        && "$RCLONE_CONFIG_PROD_ENDPOINT" == "$RCLONE_CONFIG_STAGING_ENDPOINT" ]]; then
        echo "Production and staging use the same S3 bucket and location (${PROD_S3_PATH}), aborting" 1>&2
        exit 1
    fi
}

# Major version of a PostgreSQL version string: "15.8 (Debian 15.8-1.pgdg120+1)" -> 15
pg_major() {
    printf '%s' "$1" | sed -E 's/^[^0-9]*([0-9]+).*/\1/'
}

# Must not be run in a subshell: $! would then be the PID of that subshell,
# and the tunnel would survive the kill
open_tunnel() {
    scalingo --region ${STAGING_REGION} --app ${STAGING_APP} db-tunnel -p ${TUNNEL_PORT} SCALINGO_POSTGRESQL_URL > ${WORK_DIR}/tunnel.log 2>&1 &
    TUNNEL_PID=$!
}

# Download the dump, open the tunnel to the staging database and check the versions
check_db() {
    REMOTE_DB_URL="$(require_scalingo_var "$staging_env" ${STAGING_APP} SCALINGO_POSTGRESQL_URL)" || exit 1

    WORK_DIR=${BACKUP_DIR}/prod-to-staging-`date '+%Y%m%d-%H%M%S'`
    mkdir -p ${WORK_DIR}

    # Caution, as of the Scalingo CLI app 1.39.0, the pipe separator ('|') has been replaced with a "BOX DRAWINGS LIGHT VERTICAL" ('│')
    pg_uuid=`sc_retry ${PROD_REGION} ${PROD_APP} addons | grep "PostgreSQL" | awk -F ['│'] '{print $3}' | xargs || true`
    if [[ -z "$pg_uuid" ]]; then
        echo "No PostgreSQL addon found for ${PROD_APP}" 1>&2
        exit 1
    fi

    echo "Downloading the latest backup of ${PROD_APP} to ${WORK_DIR}"
    sc_retry ${PROD_REGION} ${PROD_APP} --addon ${pg_uuid} backups-download --output ${WORK_DIR}/backup.tar.gz
    tar xzf ${WORK_DIR}/backup.tar.gz -C ${WORK_DIR}
    DUMP_FILE=`find ${WORK_DIR} -name '*.pgsql' | head -1`
    if [[ -z "$DUMP_FILE" ]]; then
        echo "No .pgsql file found in the backup archive" 1>&2
        exit 1
    fi

    LOCAL_PG_VERSION=`pg_restore --version | awk '{print $3}'`
    LOCAL_PG_MAJOR=`pg_major "${LOCAL_PG_VERSION}"`

    local dump_header
    if ! dump_header=`pg_restore -l ${DUMP_FILE} | grep -E '^; +Dumped (from|by)'`; then
        echo "pg_restore ${LOCAL_PG_VERSION} cannot read the dump," \
            "it was probably made by a newer pg_dump: install a newer postgresql-client" 1>&2
        exit 1
    fi
    PROD_PG_VERSION=`echo "${dump_header}" | sed -nE 's/^; +Dumped from database version: *//p'`
    PROD_PG_MAJOR=`pg_major "${PROD_PG_VERSION}"`
    local dump_pg_version dump_pg_major
    dump_pg_version=`echo "${dump_header}" | sed -nE 's/^; +Dumped by pg_dump version: *//p'`
    dump_pg_major=`pg_major "${dump_pg_version}"`
    if [[ -z "$PROD_PG_MAJOR" || -z "$dump_pg_major" ]]; then
        echo "Could not read the PostgreSQL versions in the header of the dump" 1>&2
        exit 1
    fi

    if (( PROD_PG_MAJOR < MIN_PROD_PG_VERSION )); then
        echo "Production PostgreSQL is ${PROD_PG_VERSION}, at least ${MIN_PROD_PG_VERSION} is required." 1>&2
        echo "The version is read in the latest backup: if PostgreSQL was upgraded since, create a new backup with" 1>&2
        echo "  scalingo --region ${PROD_REGION} --app ${PROD_APP} --addon ${pg_uuid} backups-create" 1>&2
        exit 1
    fi

    if (( LOCAL_PG_MAJOR < dump_pg_major )); then
        echo "The dump was made by pg_dump ${dump_pg_version}, but the local pg_restore is ${LOCAL_PG_VERSION}:" \
            "install a postgresql-client ${dump_pg_major} or newer" 1>&2
        exit 1
    fi

    echo "Opening the database tunnel to ${STAGING_APP}"
    open_tunnel
    trap 'kill ${TUNNEL_PID} 2> /dev/null || true' EXIT

    DB_URL=""
    local attempt=1 elapsed=0 tunnel_port
    while true; do
        # The CLI uses the next free port when the requested one is taken: read the actual one in its output
        tunnel_port=`grep -oE '127\.0\.0\.1:[0-9]+' ${WORK_DIR}/tunnel.log | head -1 | cut -d: -f2 || true`
        if [[ -n "$tunnel_port" ]]; then
            DB_URL=`echo "${REMOTE_DB_URL}" | sed -E "s#@[^/]+/#@127.0.0.1:${tunnel_port}/#"`
            psql "${DB_URL}" -Atqc "SELECT 1" &> /dev/null && break
        fi
        if ! kill -0 ${TUNNEL_PID} 2> /dev/null || [[ $elapsed -ge $TUNNEL_TIMEOUT ]]; then
            if [[ -n "$DB_URL" ]]; then
                psql "${DB_URL}" -Atqc "SELECT 1" > /dev/null || true
            fi
            kill ${TUNNEL_PID} 2> /dev/null || true
            cat ${WORK_DIR}/tunnel.log 1>&2
            if [[ $attempt -ge ${SC_RETRIES} ]]; then
                echo "Could not connect through the tunnel after ${SC_RETRIES} attempts, see the output above" 1>&2
                exit 1
            fi
            echo "Database tunnel failed (attempt ${attempt}/${SC_RETRIES}), retrying in $((attempt * 5))s" 1>&2
            sleep $((attempt * 5))
            attempt=$((attempt + 1))
            elapsed=0
            open_tunnel
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    echo "Database tunnel open on port ${tunnel_port}"

    STAGING_PG_VERSION=`psql "${DB_URL}" -Atc "SHOW server_version"`
    local staging_pg_major
    staging_pg_major=$(( `psql "${DB_URL}" -Atc "SHOW server_version_num"` / 10000 ))

    if (( staging_pg_major < MIN_STAGING_PG_VERSION )); then
        echo "Staging PostgreSQL is ${STAGING_PG_VERSION}, at least ${MIN_STAGING_PG_VERSION} is required" 1>&2
        exit 1
    fi

    if (( staging_pg_major < PROD_PG_MAJOR )); then
        echo "Staging PostgreSQL (${STAGING_PG_VERSION}) is older than production PostgreSQL (${PROD_PG_VERSION}):" \
            "restoring a dump to an older server is not supported, upgrade the staging database" 1>&2
        exit 1
    fi

    # A pg_restore newer than the server sends settings unknown to it (eg. transaction_timeout, from 17)
    if (( LOCAL_PG_MAJOR > staging_pg_major )); then
        echo "The local pg_restore (${LOCAL_PG_VERSION}) is newer than staging PostgreSQL (${STAGING_PG_VERSION}):" \
            "install a postgresql-client ${staging_pg_major}, or upgrade the staging database" 1>&2
        exit 1
    fi
}

#### Operations

restore_db() {
    # Stop the web containers so that the staging code does not write during the restoration
    WEB_AMOUNT=`sc_retry ${STAGING_REGION} ${STAGING_APP} ps | grep -cE '│ *web-[0-9]+ ' || true`
    if [[ "$WEB_AMOUNT" -gt 0 ]]; then
        sc_retry ${STAGING_REGION} ${STAGING_APP} scale web:0
        # Restart the web containers whatever happens next
        trap 'kill ${TUNNEL_PID} 2> /dev/null || true; sc_retry ${STAGING_REGION} ${STAGING_APP} scale web:${WEB_AMOUNT}' EXIT
    fi

    # Staging may run newer code than production: the tables of its newer migrations are not part
    # of the dump, so `pg_restore --clean` would leave them in place and `migrate` would then fail
    echo "Dropping all the tables of the staging database"
    local drop_statements
    drop_statements=`psql "${DB_URL}" -v ON_ERROR_STOP=1 -Atc \
        "SELECT format('DROP TABLE IF EXISTS public.%I CASCADE;', tablename) FROM pg_tables WHERE schemaname = 'public'"`
    if [[ -n "$drop_statements" ]]; then
        # The NOTICEs about the cascades are expected: the whole schema is emptied
        echo "${drop_statements}" | PGOPTIONS='-c client_min_messages=warning' psql "${DB_URL}" -v ON_ERROR_STOP=1 -q
    fi
    echo "`echo -n "${drop_statements}" | grep -c '' || true` tables dropped"

    echo "Restoring the backup"
    # Errors on extensions or comments are expected with the Scalingo user rights, and a pg_restore
    # newer than the server may send settings unknown to it (eg. transaction_timeout, from PostgreSQL 17)
    pg_restore --clean --if-exists --no-owner --no-privileges --no-comments -d "${DB_URL}" ${DUMP_FILE} \
        || echo "pg_restore reported errors (see above), check that they are only about extensions, comments" \
            "or settings unknown to the server (eg. transaction_timeout)"

    kill ${TUNNEL_PID} 2> /dev/null || true

    # Apply the migrations of the staging code, and set the Wagtail site hostname to the staging one
    # (not retried: a timeout of the CLI does not mean that the command did not run)
    scalingo --region ${STAGING_REGION} --app ${STAGING_APP} run python manage.py migrate
    scalingo --region ${STAGING_REGION} --app ${STAGING_APP} run python manage.py set_config

    if [[ "$WEB_AMOUNT" -gt 0 ]]; then
        sc_retry ${STAGING_REGION} ${STAGING_APP} scale web:${WEB_AMOUNT}
    fi
    trap - EXIT
}

sync_medias() {
    echo "Synchronizing ${PROD_S3_PATH} to ${STAGING_S3_PATH}"
    rclone sync prod:${PROD_S3_PATH} staging:${STAGING_S3_PATH} --progress
}

#### Main

if [[ $DO_MEDIAS -eq 1 ]]; then
    check_medias
fi
if [[ $DO_DB -eq 1 ]]; then
    check_db
fi
unset prod_env staging_env

if [[ $DO_DB -eq 1 && $DO_MEDIAS -eq 1 ]]; then
    REPLACED="database and media files"
elif [[ $DO_DB -eq 1 ]]; then
    REPLACED="database"
else
    REPLACED="media files"
fi

echo
echo "================================================================"
echo " From:    ${PROD_APP} (${PROD_REGION})"
if [[ $DO_MEDIAS -eq 1 ]]; then
    echo "          medias: ${PROD_S3_PATH}"
fi
echo " To:      ${STAGING_APP} (${STAGING_REGION})"
if [[ $DO_MEDIAS -eq 1 ]]; then
    echo "          medias: ${STAGING_S3_PATH}"
fi
if [[ $DO_DB -eq 1 ]]; then
    echo " PostgreSQL: prod ${PROD_PG_VERSION}, staging ${STAGING_PG_VERSION}, local pg_restore ${LOCAL_PG_VERSION}"
fi
echo
echo " The staging ${REPLACED} will be REPLACED."
echo "================================================================"
read -r -p "Type the staging app name to confirm: " CONFIRM
if [[ "$CONFIRM" != "$STAGING_APP" ]]; then
    echo "Aborted" 1>&2
    exit 1
fi

if [[ $DO_DB -eq 1 ]]; then
    restore_db
fi
if [[ $DO_MEDIAS -eq 1 ]]; then
    sync_medias
fi

echo
echo "Production ${REPLACED} copied to ${STAGING_APP}."
if [[ $DO_DB -eq 1 ]]; then
    echo "The production dump is kept in ${WORK_DIR}"
fi
