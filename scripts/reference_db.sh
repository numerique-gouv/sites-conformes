#!/bin/bash

# Manage the fictional reference bases, each in its own database and medias folder,
# without touching the usual local database:
# - monosite: site A alone;
# - monosite-b: site B alone;
# - multisite: sites A and B.
#
# Usage: reference_db.sh load|runserver|django monosite|monosite-b|multisite [django command]
#        reference_db.sh export

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

set -a
[ -f  ${SCRIPT_DIR}/../.env ] && . ${SCRIPT_DIR}/../.env && echo "Local env variables loaded"
set +a

ACTION=${1:-}
NAME=${2:-}

ALLOWED="monosite, monosite-b, multisite"
case "${ACTION}:${NAME}" in
    export:*) ;;
    *:monosite) SITES="a"; RUN_HOST="site-a.localhost" ;;
    *:monosite-b) SITES="b"; RUN_HOST="site-b.localhost" ;;
    *:multisite) SITES="a b"; RUN_HOST="site-a.localhost" ;;
    *:) echo "Missing reference base name. Allowed values: ${ALLOWED}" 1>&2; exit 1 ;;
    *) echo "Unknown reference base '${NAME}'. Allowed values: ${ALLOWED}" 1>&2; exit 1 ;;
esac

if [[ "${USE_UV:-0}" == "1" ]]; then
    PYTHON="uv run python"
else
    PYTHON="python"
fi

export PGPASSWORD="${DATABASE_PASSWORD}"

use_database() {
    REF_DATABASE_NAME="${DATABASE_NAME}_ref_${1//-/_}"
    export DATABASE_URL="postgres://${DATABASE_USER}:${DATABASE_PASSWORD}@${DATABASE_HOST}:${DATABASE_PORT}/${REF_DATABASE_NAME}"
    export MEDIA_ROOT="medias_ref_${1//-/_}"
    export S3_HOST=""
    export SF_USE_DB_STORAGE=0
    export DEBUG=True
}

reset_database() {
    echo "Creating database ${REF_DATABASE_NAME} and medias folder ${MEDIA_ROOT}"
    dropdb -U "${DATABASE_USER}" -h "${DATABASE_HOST}" -p "${DATABASE_PORT}" --force --if-exists "${REF_DATABASE_NAME}"
    createdb -U "${DATABASE_USER}" -h "${DATABASE_HOST}" -p "${DATABASE_PORT}" "${REF_DATABASE_NAME}"
    rm -rf "${SCRIPT_DIR}/../${MEDIA_ROOT}"
}

cd "${SCRIPT_DIR}/.."

case "${ACTION}" in
    load)
        use_database "${NAME}"
        reset_database
        ${PYTHON} manage.py load_reference_base ${SITES}
        echo "Run it with: just reference-runserver ${NAME}"
        ;;
    export)
        # Built in a temporary database, with both demo sites, then split into one fixture per site
        use_database "build"
        reset_database
        ${PYTHON} manage.py migrate --verbosity 0
        ${PYTHON} manage.py setup_multisite_demo
        ${PYTHON} manage.py export_reference_base
        dropdb -U "${DATABASE_USER}" -h "${DATABASE_HOST}" -p "${DATABASE_PORT}" --force "${REF_DATABASE_NAME}"
        rm -rf "${SCRIPT_DIR}/../${MEDIA_ROOT}"
        ;;
    runserver)
        use_database "${NAME}"
        ${PYTHON} manage.py runserver "${RUN_HOST}:${HOST_PORT:-8000}"
        ;;
    django)
        use_database "${NAME}"
        ${PYTHON} manage.py "${@:3}"
        ;;
    *)
        echo "Usage: $0 load|runserver|django ${ALLOWED// /} [django command], or $0 export" 1>&2
        exit 1
        ;;
esac
