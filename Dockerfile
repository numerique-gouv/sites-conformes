FROM python:3.13-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ARG CONTAINER_PORT=8000
EXPOSE ${CONTAINER_PORT}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_DIR="/app"

# Needed for docker build to succeed
ENV DATABASE_URL=postgres://user:password@localhost:5432/db

# Add new user to run the whole thing as non-root.
RUN set -ex \
    && addgroup --gid 1000 app \
    && adduser --uid 1000 --gid 1000 --home ${APP_DIR} --disabled-password app;

WORKDIR $APP_DIR

COPY pyproject.toml uv.lock ./
# Deploy in the global env of the container instead of a uv-specific venv
ENV UV_PROJECT_ENVIRONMENT="/usr/local/"
# Install dependencies only. The project itself can't be built yet: its version
# is dynamic (resolved from sites_conformes/_version.py via setuptools' attr
# directive), and that module hasn't been copied at this layer. Installing deps
# separately also keeps this layer cached across source-only changes.
RUN uv sync --locked --no-install-project

COPY --chown=app:app . .

# Now the source (incl. sites_conformes/_version.py) is present, so the dynamic
# version resolves and the project can be installed editable into the env.
RUN uv sync --locked

RUN uv run python manage.py collectstatic --no-input

RUN chown 1000:1000 -R /app
USER app
VOLUME [ "/app/medias" ]

ENTRYPOINT ["./entrypoint.sh"]
