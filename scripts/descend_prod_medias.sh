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

PROD_S3_BUCKET_NAME="$(require_scalingo_var S3_BUCKET_NAME)" || exit 1
# Absent or empty S3_LOCATION means the bucket root.
PROD_S3_LOCATION="$(scalingo_var S3_LOCATION || true)"
RCLONE_CONFIG_MYS3_REGION_NAME="$(require_scalingo_var S3_BUCKET_REGION)" || exit 1
s3_host="$(require_scalingo_var S3_HOST)" || exit 1
s3_protocol="$(scalingo_var S3_PROTOCOL || true)"
if [[ -z "$s3_protocol" ]]; then
    s3_protocol=https
fi
RCLONE_CONFIG_MYS3_ENDPOINT="${s3_protocol}://${s3_host}"
RCLONE_CONFIG_MYS3_ACCESS_KEY_ID="$(require_scalingo_var S3_KEY_ID)" || exit 1
RCLONE_CONFIG_MYS3_SECRET_ACCESS_KEY="$(require_scalingo_var S3_KEY_SECRET)" || exit 1
RCLONE_CONFIG_MYS3_PROVIDER=Other
RCLONE_CONFIG_MYS3_TYPE=s3

export PROD_S3_BUCKET_NAME PROD_S3_LOCATION \
    RCLONE_CONFIG_MYS3_REGION_NAME RCLONE_CONFIG_MYS3_ENDPOINT \
    RCLONE_CONFIG_MYS3_ACCESS_KEY_ID RCLONE_CONFIG_MYS3_SECRET_ACCESS_KEY \
    RCLONE_CONFIG_MYS3_PROVIDER RCLONE_CONFIG_MYS3_TYPE

MEDIA_BACKUP_DIR="${BACKUP_DIR}/${PROD_APP}-prod-medias/"

# Create the backup directory if it doesn't exist
test -d ${MEDIA_BACKUP_DIR} || mkdir -p ${MEDIA_BACKUP_DIR}

echo "Start copy of ${PROD_S3_BUCKET_NAME}/${PROD_S3_LOCATION} to ${MEDIA_BACKUP_DIR}"
cd ${MEDIA_BACKUP_DIR}
rclone sync mys3:${PROD_S3_BUCKET_NAME}/${PROD_S3_LOCATION} ${MEDIA_BACKUP_DIR} --progress
