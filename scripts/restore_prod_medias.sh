#!/bin/bash

# Restore the latest downloaded medias from production

# Manage environment variables
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

set -a
[ -f  ${SCRIPT_DIR}/../.env ] && . ${SCRIPT_DIR}/../.env && echo "Local env variables loaded"
set +a


if [[ -z "$BACKUP_DIR" ]]; then
    echo "Please set BACKUP_DIR to a directory outsite of the django path" 1>&2
    exit 1
fi

MEDIA_BACKUP_DIR="${BACKUP_DIR}/${PROD_APP}-prod-medias/"

echo "Moving media files from ${MEDIA_BACKUP_DIR} to ${MEDIA_ROOT:=medias}"

cd ${SCRIPT_DIR}
rm ../${MEDIA_ROOT}/* -rf

cp -rp ${MEDIA_BACKUP_DIR}/* ../${MEDIA_ROOT}/
