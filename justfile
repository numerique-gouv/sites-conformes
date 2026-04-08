set dotenv-load
set shell := ["bash", "-uc"]

# Variables initialized from env
uv_run := if env("USE_UV", "0") == "1" { "uv run" } else { "" }
docker_cmd := if env("USE_DOCKER", "0") == "1" { "docker compose exec -ti web" } else { "" }
host_proto := env("HOST_PROTO", "http")
host_url := env("HOST_URL", "localhost")
host_port := env("HOST_PORT", "8000")
script_name := env("FORCE_SCRIPT_NAME", "")

#### Default recipe

# List all recipes
default:
    @just --list

#### Main recipes
collectstatic:
    {{docker_cmd}} {{uv_run}} python manage.py collectstatic --noinput

# Compile the translation files
[group('Internationalization')]
compilemessages:
    {{docker_cmd}} {{uv_run}} django-admin compilemessages -l fr --ignore=.venv

alias csu := createsuperuser
createsuperuser:
    {{docker_cmd}} {{uv_run}} python manage.py createsuperuser

alias first-deploy := deploy
deploy:
    just migrate
    just collectstatic
    {{docker_cmd}} {{uv_run}} python manage.py create_starter_pages
    {{docker_cmd}} {{uv_run}} python manage.py import_page_templates
    {{docker_cmd}} {{uv_run}} python manage.py import_illustration_images
    just index

# Pass a django command
django +command:
    {{docker_cmd}} {{uv_run}} python manage.py {{command}}

import_domain_whitelist:
    {{docker_cmd}} {{uv_run}} python manage.py import_domain_whitelist

index:
    {{docker_cmd}} {{uv_run}} python manage.py update_index

init:
    {{docker_cmd}} uv sync --no-group dev
    just deploy

init-dev:
    {{docker_cmd}} uv sync
    just deploy
    {{docker_cmd}} {{uv_run}} pre-commit install

alias messages := makemessages
# Update the translation files
[group('Internationalization')]
makemessages:
    {{docker_cmd}} {{uv_run}} django-admin makemessages -l fr --ignore=manage.py --ignore=config --ignore=medias --ignore=__init__.py --ignore=setup.py --ignore=staticfiles  --no-location
    {{docker_cmd}} {{uv_run}} django-admin makemessages -d djangojs -l fr --ignore=config --ignore=medias --ignore=staticfiles --no-location

alias mm:= makemigrations
makemigrations app="":
    {{docker_cmd}} {{uv_run}} python manage.py makemigrations {{app}}

alias mi := migrate
migrate app="" version="":
    {{docker_cmd}} {{uv_run}} python manage.py migrate {{app}} {{version}}

mmi:
    just makemigrations
    just migrate

nginx-generate-config-file:
    cd scripts && bash nginx_generate_config_file.sh

alias rs := runserver
runserver host_url=host_url host_port=host_port:
    {{docker_cmd}} {{uv_run}} python manage.py runserver {{host_url}}:{{host_port}}

alias rg:= run_gunicorn
run_gunicorn host_url=host_url host_port=host_port script_name=script_name:
    @echo "If nginx is properly configured, the site will run on {{host_proto}}://{{host_url}}:1{{host_port}}{{script_name}}/"
    {{docker_cmd}} {{uv_run}} gunicorn config.wsgi:application --bind {{host_url}}:{{host_port}} --env SCRIPT_NAME={{script_name}}

shell:
    {{docker_cmd}} {{uv_run}} python manage.py shell

test app="":
    {{docker_cmd}} {{uv_run}} python manage.py test {{app}} --buffer --parallel --settings config.settings_test

unittest app="":
    {{docker_cmd}} {{uv_run}} python manage.py test {{app}} --settings config.settings_test

update:
    {{docker_cmd}} uv sync --no-group dev
    just deploy

upgrade:
    {{docker_cmd}} uv lock --upgrade
    {{docker_cmd}} {{uv_run}} pre-commit autoupdate
    {{docker_cmd}} npm update

web-prompt:
    {{docker_cmd}} bash

#### Production-related recipes

# Commands run by the Scalingo Procfile
[group('Production')]
scalingo-postdeploy:
    python manage.py migrate
    python manage.py create_starter_pages
    python manage.py import_page_templates
    python manage.py update_index

#### Audit-related recipes

# Run a global pre-commit
[group('Code audit')]
quality:
    {{docker_cmd}} {{uv_run}} pre-commit run --all-files

# Count lines of code per app
[group('Code audit')]
cloc:
    @for d in "config" "blog" "content_manager" "dashboard" "events" "forms" "proconnect" "templates" ; do \
    (cd "$d" && echo "$d" && cloc --vcs git); \
    done

# Evaluate test coverage then generate and open a HTML report
[group('Code audit')]
coverage app="":
    {{uv_run}} coverage run --source='.' manage.py test {{app}}
    {{uv_run}} coverage html
    firefox htmlcov/index.html

# Gives a rough estimate of the number of internal and external routes
[group('Code audit')]
routes-count:
    @{{uv_run}} python manage.py shell -v 0 -c "from django.urls import get_resolver ; \
    routes = set(v[1] for k,v in get_resolver().reverse_dict.items()) ; \
    print('Total: ' + str(len(routes))) ; \
    print('Internal: ' + str(len(list(filter(lambda k: '-admin' in k, routes))) - 3)) ; \
    print('External: ' + str(len(list(filter(lambda k: '-admin' not in k, routes))) + 3)) ;"
    @# (manually adjusting for login/logout and password reset routes)

##### Database & media management related scripts

# Get the latest local PostgreSQL backup
[group('Dev DB and medias management')]
backup-local:
    cd scripts && bash backup_local.sh

# Clears the local database
[group('Dev DB and medias management')]
clear-local-db:
    cd scripts && bash clear_local_db.sh

# Creates a bunch of example pages
[group('Dev DB and medias management')]
demo:
    just init-dev
    {{docker_cmd}} {{uv_run}} python manage.py create_demo_pages

# Descend the latest DB backup & media files of the production database
[group('Dev DB and medias management')]
descend-prod:
    cd scripts && bash descend_prod_db.sh && bash descend_prod_medias.sh

# Descend the latest DB backup of the production database
[group('Dev DB and medias management')]
descend-prod-db:
    cd scripts && bash descend_prod_db.sh

# Descend the latest media files from the production server
[group('Dev DB and medias management')]
descend-prod-medias:
    cd scripts && bash descend_prod_medias.sh

# Restore the last local database & medias backup
[group('Dev DB and medias management')]
restore-local:
    cd scripts && bash restore_local_db.sh && bash restore_local_medias.sh

# Restore the last local database backup
[group('Dev DB and medias management')]
restore-local-db:
    cd scripts && bash restore_local_db.sh
    {{docker_cmd}} {{uv_run}} python manage.py set_config

# Restore the last local medias backup
[group('Dev DB and medias management')]
restore-local-medias:
    cd scripts && bash restore_local_medias.sh

# Restore the last downloaded backup & media files from production
[group('Dev DB and medias management')]
restore-prod:
    cd scripts && bash restore_prod_db.sh && bash restore_prod_medias.sh
    {{docker_cmd}} {{uv_run}} python manage.py set_config

# Restore the last downloaded backup of the production database
[group('Dev DB and medias management')]
restore-prod-db:
    cd scripts && bash restore_prod_db.sh
    {{docker_cmd}} {{uv_run}} python manage.py set_config

# Restore the last downloaded media files
[group('Dev DB and medias management')]
restore-prod-medias:
    cd scripts && bash restore_prod_medias.sh
