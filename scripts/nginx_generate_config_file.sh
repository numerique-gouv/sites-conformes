#!/bin/bash
# Generate the nginx config file with the env variable

# Manage environment variables
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
export BASE_PATH=$(dirname ${SCRIPT_DIR})

set -a
[ -f  ${SCRIPT_DIR}/../.env ] && . ${SCRIPT_DIR}/../.env && echo "Local env variables loaded"
set +a

# Manually specifying the allowed variables for substitions to avoid inference with dollar signs in the conf
envsubst '${BASE_PATH} ${FORCE_SCRIPT_NAME} ${HOST_PORT} ${HOST_URL}' \
< ${SCRIPT_DIR}/sample_conf_files/nginx.conf.template > /tmp/sites-conformes.conf \
&& echo "Nginx config file generated."

echo -e "\nPlease review and complete the generated file with:\n"
echo -e  "    vi /tmp/sites-conformes.conf"
echo -e  "\nWhen you are done, you can install and test it with:\n"
echo -e  "    sudo cp /tmp/sites-conformes.conf /etc/nginx/sites-available/sites-conformes.conf"
echo -e  "    sudo ln -s /etc/nginx/sites-available/sites-conformes.conf /etc/nginx/sites-enabled/sites-conformes.conf"
echo -e  "    sudo nginx -t"
echo -e  "\nIf everything is ok, you can reload the Nginx service:\n"
echo -e  "    sudo service nginx reload"
