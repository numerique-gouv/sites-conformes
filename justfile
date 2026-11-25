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
[private]
default:
    @just --list

#### Installation & update recipes

# Create .env from .env.example with a generated SECRET_KEY (never overwrites an existing .env)
[group('Installation')]
setup-env:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -f .env ]; then
        echo ".env already exists, nothing was overwritten."
        exit 0
    fi
    cp .env.example .env
    python3 -c "import secrets,pathlib; c='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#%^&*(-_=+)'; k=''.join(secrets.choice(c) for _ in range(50)); p=pathlib.Path('.env'); p.write_text('\n'.join('SECRET_KEY='+k if l.startswith('SECRET_KEY=') else l for l in p.read_text().splitlines())+'\n')"
    echo "✅ .env created with a generated SECRET_KEY."

# Create the PostgreSQL user and database defined in .env (DATABASE_USER / DATABASE_PASSWORD / DATABASE_NAME)
[group('Installation')]
setup-db:
    #!/usr/bin/env bash
    set -euo pipefail
    psql -U postgres -c "CREATE USER ${DATABASE_USER} WITH CREATEDB LOGIN PASSWORD '${DATABASE_PASSWORD}';"
    psql -U postgres -c "CREATE DATABASE ${DATABASE_NAME} OWNER ${DATABASE_USER};"
    echo "✅ PostgreSQL user and database created (${DATABASE_USER} / ${DATABASE_NAME})."

# Install the dependencies (without the dev ones) and deploy
[group('Installation')]
init:
    {{docker_cmd}} uv sync --no-group dev
    just deploy

# Install the dependencies (with the dev ones), deploy and install the pre-commit hooks
[group('Installation')]
init-dev:
    {{docker_cmd}} uv sync
    just deploy
    {{docker_cmd}} {{uv_run}} prek install --overwrite

alias first-deploy := deploy
# Collect the static files, migrate, create the starter pages and page templates, update the search index
[group('Installation')]
deploy:
    just collectstatic
    just migrate
    {{docker_cmd}} {{uv_run}} python manage.py create_starter_pages
    {{docker_cmd}} {{uv_run}} python manage.py import_page_templates
    just index

# Sync the dependencies (without the dev ones) and deploy
[group('Installation')]
update:
    {{docker_cmd}} uv sync --no-group dev
    just deploy

# Upgrade the Python, pre-commit and npm dependencies
[group('Installation')]
upgrade:
    {{docker_cmd}} uv lock --upgrade
    {{docker_cmd}} {{uv_run}} prek update --cooldown-days 7
    {{docker_cmd}} npm update
    just sync-tarteaucitron

# Re-vendor the TarteAuCitron JS library from the installed npm package
[group('Installation')]
sync-tarteaucitron:
    {{docker_cmd}} npm ci
    cd scripts && bash sync_tarteaucitron.sh

#### Django-related recipes

# Collect the static files
[group('Django')]
collectstatic:
    {{docker_cmd}} {{uv_run}} python manage.py collectstatic --noinput

alias csu := createsuperuser
# Create an admin user
[group('Django')]
createsuperuser:
    {{docker_cmd}} {{uv_run}} python manage.py createsuperuser

# Pass a django command (or list available django commands)
[group('Django')]
django +command="":
    {{docker_cmd}} {{uv_run}} python manage.py {{command}}

# Import the whitelist of email domains allowed to log in with ProConnect
[group('Django')]
import_domain_whitelist:
    {{docker_cmd}} {{uv_run}} python manage.py import_domain_whitelist

# Update the search index
[group('Django')]
index:
    {{docker_cmd}} {{uv_run}} python manage.py update_index

alias mm := makemigrations
# Create the migrations (for all the apps, or for a given app)
[group('Django')]
makemigrations app="":
    {{docker_cmd}} {{uv_run}} python manage.py makemigrations {{app}}

alias mi := migrate
# Apply the migrations (for all the apps, or for a given app and version)
[group('Django')]
migrate app="" version="":
    {{docker_cmd}} {{uv_run}} python manage.py migrate {{app}} {{version}}

# Create then apply the migrations
[group('Django')]
mmi:
    just makemigrations
    just migrate

# Open a Django shell
[group('Django')]
shell:
    {{docker_cmd}} {{uv_run}} python manage.py shell

# Open a bash prompt in the web container
[group('Django')]
web-prompt:
    {{docker_cmd}} bash

#### Local server recipes

alias rs := runserver
# Run the Django development server
[group('Local server')]
runserver host_url=host_url host_port=host_port:
    {{docker_cmd}} {{uv_run}} python manage.py runserver {{host_url}}:{{host_port}}

alias rg:= run_gunicorn
# Run the site with gunicorn (behind nginx)
[group('Local server')]
run_gunicorn host_url=host_url host_port=host_port script_name=script_name:
    @echo "If nginx is properly configured, the site will run on {{host_proto}}://{{host_url}}:1{{host_port}}{{script_name}}/"
    {{docker_cmd}} {{uv_run}} gunicorn config.wsgi:application --bind {{host_url}}:{{host_port}} --env SCRIPT_NAME={{script_name}}

# Generate the nginx configuration file used with run_gunicorn
[group('Local server')]
nginx-generate-config-file:
    cd scripts && bash nginx_generate_config_file.sh

#### Test-related recipes

# Run the unit tests in parallel (for all the apps, or for a given app)
[group('Tests')]
test app="":
    {{docker_cmd}} {{uv_run}} python manage.py test {{app}} --buffer --parallel --settings config.settings_test

# Run the unit tests sequentially (for all the apps, or for a given app)
[group('Tests')]
unittest app="":
    {{docker_cmd}} {{uv_run}} python manage.py test {{app}} --settings config.settings_test

# Run the Playwright end-to-end tests in Docker, on a throwaway database (extra args go to Playwright, see CONTRIBUTING.md)
[group('Tests')]
e2e *args:
    env UID=$(id -u) GID=$(id -g) docker compose --profile e2e run --rm playwright npx playwright test {{args}}

# Stop the end-to-end test containers and reset their database (leaves the dev containers and volumes alone)
[group('Tests')]
e2e-down:
    docker compose --profile e2e rm --stop --force --volumes db-e2e web-e2e

# Prepare the e2e database: migrations, starter, demo and e2e pages (run by the web-e2e container)
[group('Tests')]
e2e-setup:
    just deploy
    {{uv_run}} python manage.py create_demo_pages
    {{uv_run}} python manage.py create_e2e_pages

#### Internationalization-related recipes

# Compile the translation files
[group('Internationalization')]
compilemessages:
    {{docker_cmd}} {{uv_run}} python manage.py compilemessages -l fr --ignore=.venv*

alias messages := makemessages
# Update the translation files
[group('Internationalization')]
makemessages:
    {{docker_cmd}} {{uv_run}} python manage.py makemessages -l fr --ignore=manage.py --ignore=config --ignore=medias --ignore=__init__.py --ignore=setup.py --ignore=staticfiles --ignore=docs --ignore=node_modules --no-location
    {{docker_cmd}} {{uv_run}} python manage.py makemessages -d djangojs -l fr --ignore=config --ignore=medias --ignore=staticfiles --ignore=docs --ignore=node_modules --no-location

#### Production-related recipes

# Commands run by the Scalingo Procfile
[group('Production')]
scalingo-postdeploy:
    python manage.py migrate
    python manage.py create_starter_pages
    python manage.py import_page_templates
    python manage.py update_index

# Roll a Scalingo app back to a DB backup and to the code of a given git ref
[group('Production')]
scalingo-rollback app region="-" ref="":
    cd scripts && bash rollback_scalingo.sh {{app}} {{region}} {{ref}}

# Copy the latest DB backup & the media files of the production app to the staging app (options: --db-only, --medias-only)
[group('Production')]
descend-prod-to-staging *options:
    cd scripts && bash descend_prod_to_staging.sh {{options}}

#### Audit-related recipes

# Run the Django system check framework
[group('Code audit')]
check +apps="":
    {{docker_cmd}} {{uv_run}} python manage.py check {{apps}}

# Run a global quality check
[group('Code audit')]
quality:
    {{docker_cmd}} {{uv_run}} prek run --all-files

# Count lines of code per app. Requires cloc (see CONTRIBUTING.md).
[group('Code audit')]
cloc:
    @for d in "config" "blog" "content_manager" "dashboard" "events" "forms" "numerique_gouv" "proconnect" "templates" ; do \
    (cd "$d" && echo "$d" && cloc --vcs git); \
    done

# Evaluate test coverage then generate and open a HTML report
[group('Code audit')]
coverage app="":
    {{uv_run}} coverage run --source='.' manage.py test {{app}}
    {{uv_run}} coverage html
    firefox htmlcov/index.html

# Give a rough estimate of the number of internal and external routes
[group('Code audit')]
routes-count:
    @{{uv_run}} python manage.py shell -v 0 -c "from django.urls import get_resolver ; \
    routes = set(v[1] for k,v in get_resolver().reverse_dict.items()) ; \
    print('Total: ' + str(len(routes))) ; \
    print('Internal: ' + str(len(list(filter(lambda k: '-admin' in k, routes))) - 3)) ; \
    print('External: ' + str(len(list(filter(lambda k: '-admin' not in k, routes))) + 3)) ;"
    @# (manually adjusting for login/logout and password reset routes)

##### Database & media management related scripts

# Back up the local database and media files
[group('Dev DB and media management')]
backup-local:
    cd scripts && bash backup_local.sh

# Clear the local database
[group('Dev DB and media management')]
clear-local-db:
    cd scripts && bash clear_local_db.sh

# Create a bunch of example pages
[group('Dev DB and media management')]
demo:
    just init-dev
    {{docker_cmd}} {{uv_run}} python manage.py create_demo_pages

# Download the latest DB backup and media files of the production app
[group('Dev DB and media management')]
descend-prod:
    cd scripts && bash descend_prod_db.sh && bash descend_prod_medias.sh

# Download the latest DB backup of the production app
[group('Dev DB and media management')]
descend-prod-db:
    cd scripts && bash descend_prod_db.sh

# Download the latest media files from the production app
[group('Dev DB and media management')]
descend-prod-medias:
    cd scripts && bash descend_prod_medias.sh

# Restore the last local database and media backup
[group('Dev DB and media management')]
restore-local:
    cd scripts && bash restore_local_db.sh && bash restore_local_medias.sh

# Restore the last local database backup
[group('Dev DB and media management')]
restore-local-db:
    cd scripts && bash restore_local_db.sh
    {{docker_cmd}} {{uv_run}} python manage.py set_config

# Restore the last local media backup
[group('Dev DB and media management')]
restore-local-medias:
    cd scripts && bash restore_local_medias.sh

# Restore the last downloaded backup & media files from production
[group('Dev DB and media management')]
restore-prod:
    cd scripts && bash restore_prod_db.sh && bash restore_prod_medias.sh
    {{docker_cmd}} {{uv_run}} python manage.py set_config

# Restore the last downloaded backup of the production database
[group('Dev DB and media management')]
restore-prod-db:
    cd scripts && bash restore_prod_db.sh
    {{docker_cmd}} {{uv_run}} python manage.py set_config

# Restore the last downloaded media files
[group('Dev DB and media management')]
restore-prod-medias:
    cd scripts && bash restore_prod_medias.sh
