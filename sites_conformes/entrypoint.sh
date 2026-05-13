#!/bin/sh -l
set -ex

export USE_UV=0
export USE_DOCKER=0 # Commands run from inside docker shouldn't be prefixed

just deploy

if [ "$DEBUG" = "True" ]; then
    python manage.py runserver 0.0.0.0:$CONTAINER_PORT
else
    gunicorn config.wsgi:application --bind 0.0.0.0:$CONTAINER_PORT
fi

exec "$@"
