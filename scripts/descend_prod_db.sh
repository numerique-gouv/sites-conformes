#! /bin/bash

# Get the latest PostgreSQL backup for the production app

# Manage environment variables
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

set -a
[ -f  ${SCRIPT_DIR}/../.env ] && . ${SCRIPT_DIR}/../.env && echo "Local env variables loaded"
set +a

if [[ -z "$PROD_APP" ]]; then
    echo "Please set PROD_APP" 1>&2
    exit 1
fi

PROD_REGION=${PROD_REGION:-osc-fr1}

if [[ -z "$BACKUP_DIR" ]]; then
    echo "Please set BACKUP_DIR to a directory outsite of the django path" 1>&2
    exit 1
fi

# Caution, as of the Scalingo CLI app 1.39.0, the pipe separator ('|') has been replaced with a "BOX DRAWINGS LIGHT VERTICAL" ('│')
pg_uuid=`scalingo --region "${PROD_REGION}" --app "${PROD_APP}" addons | grep "PostgreSQL" | awk -F ['│'] '{print $3}' | xargs`

echo "Backup UUID: ${pg_uuid}"

cd ${BACKUP_DIR}
scalingo --region "${PROD_REGION}" --app "${PROD_APP}" --addon $pg_uuid backups-download
echo "Prod backup saved at ${BACKUP_DIR}"
