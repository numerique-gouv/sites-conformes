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

MEDIA_BACKUP_FILE=`ls ${BACKUP_DIR}/sites-conformes-local-medias-*.tar.gz -c | head -1`
if [[ ! -f "${MEDIA_BACKUP_FILE}" ]]; then
    echo "ERROR: media backup file not found. Cannot restore medias." >&2
    exit 1
fi

BASE_PATH="${SCRIPT_DIR}/.."
cd ${BASE_PATH}
echo "Extracting ${MEDIA_BACKUP_FILE} into ${MEDIA_ROOT:=medias}..."
if ! (rm -rf "${MEDIA_ROOT:?}"/* && tar xzf "${MEDIA_BACKUP_FILE}"); then
    echo "ERROR: media extraction failed (tar exit $?)" >&2
    exit 1
fi
member_count=$(find "${MEDIA_ROOT}" -type f 2>/dev/null | wc -l | awk '{print $1}')
echo "Media restoration succeeded (${member_count} files in ${MEDIA_ROOT})"
