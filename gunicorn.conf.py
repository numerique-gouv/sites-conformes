# Loaded automatically by gunicorn from the working directory (Procfile,
# entrypoint.sh, `just run_gunicorn`, systemd). Every value can be overridden
# with a GUNICORN_* environment variable.
import os

# Load the app in the master before forking: faster worker (re)start,
# shared memory between workers.
preload_app = True

worker_class = "gthread"
workers = int(os.environ.get("GUNICORN_WORKERS") or os.environ.get("WEB_CONCURRENCY") or 2)
threads = int(os.environ.get("GUNICORN_THREADS", 4))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))

# Recycle workers periodically to contain memory leaks; the jitter spreads
# restarts so workers don't all recycle at once.
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", 10000))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", 2500))
