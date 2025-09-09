set dotenv-load
set shell := ["bash", "-uc"]

# Variables initialized from env
uv_run := if env("USE_UV", "0") == "1" { "uv run" } else { "" }
docker_cmd := if env("USE_DOCKER", "0") == "1" { "docker compose exec -ti web" } else { "" }
host_url := env("HOST_URL", "localhost")
host_port := env("HOST_PORT", "8000")

#### Default recipe

# List all recipes
default:
    @just --list

#### Main recipes

collectstatic:
    {{docker_cmd}} {{uv_run}} python manage.py collectstatic --noinput

createsuperuser:
    {{docker_cmd}} {{uv_run}} python manage.py createsuperuser

demo:
    just init
    {{docker_cmd}} {{uv_run}} python manage.py create_demo_pages

alias first-deploy := deploy
deploy:
    just migrate
    just collectstatic
    {{docker_cmd}} {{uv_run}} python manage.py create_starter_pages
    {{docker_cmd}} {{uv_run}} python manage.py import_page_templates
    just index

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
makemessages:
    {{docker_cmd}} {{uv_run}} django-admin makemessages -l fr --ignore=manage.py --ignore=config --ignore=medias --ignore=__init__.py --ignore=setup.py --ignore=staticfiles
    {{docker_cmd}} {{uv_run}} django-admin makemessages -d djangojs -l fr --ignore=config --ignore=medias --ignore=staticfiles

alias mm:= makemigrations
makemigrations app="":
    {{docker_cmd}} {{uv_run}} python manage.py makemigrations {{app}}

alias mi := migrate
migrate app="" version="":
    {{docker_cmd}} {{uv_run}} python manage.py migrate {{app}} {{version}}

mmi:
    just makemigrations
    just migrate

quality:
    {{docker_cmd}} {{uv_run}} pre-commit run --all-files

alias rs := runserver
runserver host_url=host_url host_port=host_port:
    {{docker_cmd}} {{uv_run}} python manage.py runserver {{host_url}}:{{host_port}}

scalingo-postdeploy:
    python manage.py migrate
    python manage.py create_starter_pages
    python manage.py import_page_templates
    python manage.py update_index

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

#### Audit-related recipes

# Count lines of code per app
cloc:
    @for d in "config" "blog" "content_manager" "dashboard" "events" "forms" "proconnect" "templates" ; do \
    (cd "$d" && echo "$d" && cloc --vcs git); \
    done

# Evaluate test coverage then generate and open a HTML report
coverage app="":
    {{uv_run}} coverage run --source='.' manage.py test {{app}}
    {{uv_run}} coverage html
    firefox htmlcov/index.html

# Gives a rough estimate of the number of internal and external routes
routes-count:
    @{{uv_run}} python manage.py shell -v 0 -c "from django.urls import get_resolver ; \
    routes = set(v[1] for k,v in get_resolver().reverse_dict.items()) ; \
    print('Total: ' + str(len(routes))) ; \
    print('Internal: ' + str(len(list(filter(lambda k: '-admin' in k, routes))) - 3)) ; \
    print('External: ' + str(len(list(filter(lambda k: '-admin' not in k, routes))) + 3)) ;"
    @# (manually adjusting for login/logout and password reset routes)
