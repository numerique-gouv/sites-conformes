#! /bin/bash

# Get the user-imported medias from the production app's S3 storage

# Manage environment variables
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

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

MEDIA_BACKUP_DIR="${BACKUP_DIR}/${PROD_APP}-prod-medias/"

# Create the backup directory if it doesn't exist
test -d ${MEDIA_BACKUP_DIR} || mkdir -p ${MEDIA_BACKUP_DIR}

echo "Start copy of ${PROD_S3_BUCKET_NAME}/${PROD_S3_LOCATION} to ${MEDIA_BACKUP_DIR}"
cd ${MEDIA_BACKUP_DIR}
rclone sync mys3:${PROD_S3_BUCKET_NAME}/${PROD_S3_LOCATION} ${MEDIA_BACKUP_DIR} --progress
