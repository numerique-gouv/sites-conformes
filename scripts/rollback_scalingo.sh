#!/bin/bash

# Roll a Scalingo app back to a database backup and to the code of a given git ref
#
# Usage: rollback_scalingo.sh APP [REGION=osc-fr1] [REF]
#
# REGION can be "-" to use the default region while passing a REF.
#
# REPO_URL_BASE (default: https://github.com/numerique-gouv/sites-conformes) can point to a fork.
#
# By default, REF is the code of the last successful deployment before the backup:
# the content of the backup may not be readable by older code.
#
# Tables created after the chosen backup (by newer migrations) are not part of the dump,
# so `pg_restore --clean` would leave them in place: they are detected and dropped first.

# Manage environment variables
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

set -a
[ -f  ${SCRIPT_DIR}/../.env ] && . ${SCRIPT_DIR}/../.env && echo "Local env variables loaded"
set +a

set -euo pipefail

APP=${1:-}
REGION=${2:-osc-fr1}
if [[ "$REGION" == "-" ]]; then
    REGION=osc-fr1
fi
REF=${3:-}
TUNNEL_PORT=${TUNNEL_PORT:-10000}

REPO_URL_BASE=${REPO_URL_BASE:-https://github.com/numerique-gouv/sites-conformes}
REPO_URL_BASE=${REPO_URL_BASE%/}
REPO_URL="${REPO_URL_BASE}.git"

if [[ -z "$APP" ]]; then
    echo "Usage: $0 APP [REGION=osc-fr1] [REF]" 1>&2
    exit 1
fi

if [[ -z "${BACKUP_DIR:-}" ]]; then
    echo "Please set BACKUP_DIR to a directory outsite of the django path" 1>&2
    exit 1
fi

for cmd in scalingo pg_restore psql curl git; do
    if ! command -v $cmd &> /dev/null; then
        echo "Missing command: ${cmd}" 1>&2
        exit 1
    fi
done

# Minimum delay between two calls to the Scalingo API, as close calls sometimes fail
SC_MIN_INTERVAL_MS=${SC_MIN_INTERVAL_MS:-1000}

now_ms() {
    echo $(( $(date +%s%N) / 1000000 ))
}

sc() {
    # sc is often called in subshells: the time of the last call is kept in a file
    local last_call_file=${WORK_DIR}/.sc_last_call
    local last_call=`cat ${last_call_file} 2> /dev/null || echo 0`
    local wait_ms=$(( last_call + SC_MIN_INTERVAL_MS - $(now_ms) ))
    if (( wait_ms > 0 )); then
        sleep `printf '%d.%03d' $((wait_ms / 1000)) $((wait_ms % 1000))`
    fi
    now_ms > ${last_call_file}
    scalingo --region ${REGION} --app ${APP} "$@"
}

# The Scalingo API sometimes times out: retry the commands that can safely be run twice
SC_RETRIES=${SC_RETRIES:-3}

sc_retry() {
    local attempt
    local output_file=${WORK_DIR}/.sc_last_output
    for attempt in $(seq 1 ${SC_RETRIES}); do
        if [[ -t 1 ]]; then
            # Keep the terminal as stdout so that the CLI can display its progress bars
            if sc "$@"; then
                return 0
            fi
        else
            # The CLI writes its errors on stdout: only pass on the output of the attempt that
            # succeeds, so that the errors end up on stderr instead of in the captured output
            if sc "$@" > ${output_file}; then
                cat ${output_file}
                return 0
            fi
            cat ${output_file} 1>&2
        fi
        if [[ $attempt -lt ${SC_RETRIES} ]]; then
            echo "Scalingo command failed (attempt ${attempt}/${SC_RETRIES}), retrying in $((attempt * 5))s: $*" 1>&2
            sleep $((attempt * 5))
        fi
    done
    echo "Scalingo command failed after ${SC_RETRIES} attempts: $*" 1>&2
    return 1
}

WORK_DIR=${BACKUP_DIR}/rollback-${APP}-`date '+%Y%m%d-%H%M%S'`
mkdir -p ${WORK_DIR}

# Caution, as of the Scalingo CLI app 1.39.0, the pipe separator ('|') has been replaced with a "BOX DRAWINGS LIGHT VERTICAL" ('│')
pg_uuid=`sc_retry addons | grep "PostgreSQL" | awk -F ['│'] '{print $3}' | xargs`
if [[ -z "$pg_uuid" ]]; then
    echo "No PostgreSQL addon found for ${APP}" 1>&2
    exit 1
fi
echo "PostgreSQL addon: ${pg_uuid}"

# Choose the backup
echo
echo "Recent deployments:"
DEPLOYMENTS=`sc_retry deployments | sed 's/\x1b\[[0-9;]*m//g'`
echo "${DEPLOYMENTS}" | head -n 12
echo
echo "Available backups:"
# Fetched once: the list is also used to decide whether a safety backup is needed
BACKUPS=`sc_retry --addon ${pg_uuid} backups`
echo "${BACKUPS}"
if [[ -z "${BACKUP_ID:-}" ]]; then
    echo
    read -r -p "ID of the backup to restore (it must predate the deployment to roll back): " BACKUP_ID
fi
if [[ -z "$BACKUP_ID" ]]; then
    echo "No backup chosen, aborting" 1>&2
    exit 1
fi

# Code that was running when the backup was made: the last successful deployment before it
# (the dates of the deployments are in UTC)
backup_date=`echo "${BACKUPS}" | sed 's/\x1b\[[0-9;]*m//g' \
    | awk -F '│' -v id="${BACKUP_ID}" 'index($2, id) {print $3; exit}' | xargs`
if [[ -z "$backup_date" ]]; then
    echo "Backup ${BACKUP_ID} not found in the list of backups" 1>&2
    exit 1
fi
backup_timestamp=`date -d "${backup_date}" +%s`
BACKUP_REF=""
while IFS='│' read -r _ _ deployment_date _ _ deployment_ref deployment_status _; do
    deployment_status=`echo ${deployment_status}`
    deployment_date=`echo ${deployment_date}`
    if [[ "$deployment_status" == "success" ]] \
        && (( `date -d "${deployment_date} UTC" +%s` <= backup_timestamp )); then
        BACKUP_REF=`echo ${deployment_ref}`
        break
    fi
done < <(echo "${DEPLOYMENTS}" | grep -E '│ *[0-9]{4}/[0-9]{2}/[0-9]{2} ')
if [[ -z "$REF" ]]; then
    if [[ -z "$BACKUP_REF" ]]; then
        echo "No successful deployment found before the backup (${backup_date}) in the recent deployments," \
            "pass the git ref to deploy as a parameter" 1>&2
        exit 1
    fi
    REF=${BACKUP_REF}
fi

REPO_ARCHIVE_URL="${REPO_URL_BASE}/archive/${REF}.tar.gz"
if ! curl -sfIL -o /dev/null ${REPO_ARCHIVE_URL}; then
    echo "Git ref ${REF} not found (${REPO_ARCHIVE_URL})" 1>&2
    exit 1
fi

# Download and extract the backup
echo "Downloading backup ${BACKUP_ID} to ${WORK_DIR}"
sc_retry --addon ${pg_uuid} backups-download --backup ${BACKUP_ID} --output ${WORK_DIR}/backup.tar.gz
tar xzf ${WORK_DIR}/backup.tar.gz -C ${WORK_DIR}
DUMP_FILE=`find ${WORK_DIR} -name '*.pgsql' | head -1`
if [[ -z "$DUMP_FILE" ]]; then
    echo "No .pgsql file found in the backup archive" 1>&2
    exit 1
fi

# Read the tables of the dump once, and check that this pg_restore can read it at all:
# otherwise every table of the database would be taken for a table created since the backup
if ! pg_restore -l ${DUMP_FILE} > ${WORK_DIR}/dump.list; then
    echo "pg_restore `pg_restore --version | awk '{print $3}'` cannot read the dump," \
        "it was probably made by a newer PostgreSQL: install a matching postgresql-client" 1>&2
    exit 1
fi
DUMP_TABLES=`awk '$4 == "TABLE" && $5 == "public" {print $6}' ${WORK_DIR}/dump.list | LC_ALL=C sort -u`
if [[ -z "$DUMP_TABLES" ]]; then
    echo "No table found in the dump, see ${WORK_DIR}/dump.list" 1>&2
    exit 1
fi

# Open the database tunnel
REMOTE_DB_URL=`sc_retry env-get SCALINGO_POSTGRESQL_URL`
# Seconds to wait for each attempt: the CLI can take about 30s to get its access token
TUNNEL_TIMEOUT=${TUNNEL_TIMEOUT:-60}

# Must not be run in a subshell (nor the sc function in the background):
# $! would then be the PID of that subshell, and the tunnel would survive the kill
open_tunnel() {
    scalingo --region ${REGION} --app ${APP} db-tunnel -p ${TUNNEL_PORT} SCALINGO_POSTGRESQL_URL > ${WORK_DIR}/tunnel.log 2>&1 &
    TUNNEL_PID=$!
}

echo "Opening the database tunnel"
open_tunnel
trap 'kill ${TUNNEL_PID} 2> /dev/null || true' EXIT

DB_URL=""
attempt=1
elapsed=0
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

# Tables present in the database but absent from the dump
# (sort and comm must share the same collation: the C locale avoids locale-dependent orders)
extra_tables() {
    LC_ALL=C comm -13 \
        <(echo "${DUMP_TABLES}") \
        <(psql "${DB_URL}" -Atc "SELECT tablename FROM pg_tables WHERE schemaname = 'public'" | LC_ALL=C sort -u)
}
EXTRA_TABLES=`extra_tables`

echo
echo "================================================================"
echo " App:     ${APP} (${REGION})"
echo " Backup:  ${BACKUP_ID}"
echo " Code:    ${REF}"
if [[ "$REF" != "$BACKUP_REF" ]]; then
    echo "          /!\\ the code deployed when the backup was made is ${BACKUP_REF:-unknown}," \
        "the content of the backup may not be readable by older code"
fi
echo " Tables created since the backup, to be dropped:"
echo "${EXTRA_TABLES:-  (none)}" | sed 's/^/   /'
echo
echo " The current database will be REPLACED by the backup."
echo "================================================================"
read -r -p "Type the app name to confirm: " CONFIRM
if [[ "$CONFIRM" != "$APP" ]]; then
    echo "Aborted" 1>&2
    exit 1
fi

backup_ids() {
    echo "$1" | sed 's/\x1b\[[0-9;]*m//g' | awk -F '│' '$2 ~ /[0-9a-f]{24}/ {gsub(/ /, "", $2); print $2}'
}

# Wait for a backup absent from the list fetched at the beginning to be done
wait_for_safety_backup() {
    local known_ids=`backup_ids "${BACKUPS}"`
    local i list backup_id status
    for i in $(seq 1 180); do
        list=`sc_retry --addon ${pg_uuid} backups | sed 's/\x1b\[[0-9;]*m//g'`
        backup_id=`backup_ids "${list}" | grep -vxF "${known_ids}" | head -1 || true`
        if [[ -z "$backup_id" ]]; then
            if [[ $i -ge 6 ]]; then
                echo "No safety backup was created, run the script again" 1>&2
                exit 1
            fi
        else
            status=`echo "${list}" | awk -F '│' -v id="${backup_id}" 'index($2, id) {gsub(/ /, "", $5); print $5}'`
            case "$status" in
                done)
                    echo "Safety backup ${backup_id} done"
                    return 0
                    ;;
                error|failed)
                    echo "The safety backup ${backup_id} failed (${status})" 1>&2
                    exit 1
                    ;;
            esac
            echo "Safety backup ${backup_id}: ${status}, waiting"
        fi
        sleep 10
    done
    echo "The safety backup is still not done after 30 minutes, aborting" 1>&2
    exit 1
}

# Skip the safety backup if a completed one is recent enough (the restored backup does not count)
SAFETY_BACKUP_MAX_AGE=$((6 * 3600))
last_backup_date=`echo "${BACKUPS}" | sed 's/\x1b\[[0-9;]*m//g' \
    | awk -F '│' -v restored="${BACKUP_ID}" '$5 ~ /done/ && (restored == "" || !index($2, restored)) {print $3; exit}' | xargs`
if [[ -n "$last_backup_date" ]] \
    && (( $(date +%s) - $(date -d "$last_backup_date" +%s) < SAFETY_BACKUP_MAX_AGE )); then
    echo "Skipping the safety backup, a backup was made less than 6 hours ago (${last_backup_date})"
else
    echo "Creating a safety backup of the current database"
    if ! sc --addon ${pg_uuid} backups-create; then
        # The CLI follows the backup until it is done and can time out meanwhile, although the
        # backup was created: look for it in the list rather than create another one
        echo "Checking whether the safety backup was created anyway" 1>&2
        wait_for_safety_backup
    fi
fi

# Stop the web containers so that the current code does not write during the restoration
WEB_AMOUNT=`sc_retry ps | grep -cE '│ *web-[0-9]+ ' || true`
if [[ "$WEB_AMOUNT" -eq 0 ]]; then
    read -r -p "Could not read the number of web containers, how many should be restarted? " WEB_AMOUNT
fi
sc_retry scale web:0

if [[ -n "$EXTRA_TABLES" ]]; then
    echo "Dropping the tables created since the backup"
    psql "${DB_URL}" -v ON_ERROR_STOP=1 -c "DROP TABLE IF EXISTS $(echo ${EXTRA_TABLES} | sed 's/ /, /g') CASCADE;"
fi

echo "Restoring the backup"
# Errors on extensions or comments are expected with the Scalingo user rights, and a pg_restore
# newer than the server sends settings unknown to it (eg. transaction_timeout, from PostgreSQL 17)
pg_restore --clean --if-exists --no-owner --no-privileges --no-comments -d "${DB_URL}" ${DUMP_FILE} \
    || echo "pg_restore reported errors (see above), check that they are only about extensions, comments" \
        "or settings unknown to the server (eg. transaction_timeout)"

REMAINING_TABLES=`extra_tables`
if [[ -n "$REMAINING_TABLES" ]]; then
    echo "Some tables are still absent from the backup, aborting before deploying:" 1>&2
    echo "${REMAINING_TABLES}" 1>&2
    exit 1
fi

kill ${TUNNEL_PID} 2> /dev/null || true

# The database is restored: restart the web containers even if the deployment fails
trap 'sc_retry scale web:${WEB_AMOUNT}' EXIT

echo "Deploying ${REF}"
# Archive deployments can fail in the apt buildpack: go through the GitHub integration when possible
# (it can only deploy branches: use a branch whose head is REF when REF is a commit)
if git ls-remote --exit-code --heads ${REPO_URL} ${REF} &> /dev/null; then
    DEPLOY_BRANCH=${REF}
else
    DEPLOY_BRANCH=`git ls-remote --heads ${REPO_URL} \
        | awk -v ref="${REF}" 'index($1, ref) == 1 {sub("refs/heads/", "", $2); print $2; exit}' || true`
fi
if [[ -n "$DEPLOY_BRANCH" ]] && sc integration-link 2> /dev/null | grep -q "Repository:"; then
    sc integration-link-manual-deploy --follow ${DEPLOY_BRANCH}
else
    sc deploy ${REPO_ARCHIVE_URL} ${REF}
fi

echo
echo "Rollback done. Next steps:"
echo " - check the migrations: scalingo --region ${REGION} --app ${APP} run python manage.py showmigrations"
echo " - if a GitHub integration with auto-deploy is linked (scalingo --region ${REGION} --app ${APP} integration-link),"
echo "   the next push on its branch will deploy that code again"
echo " - media files uploaded after the backup are still on the S3 bucket, but no longer referenced"
