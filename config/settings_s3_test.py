from config.settings import *  # NOSONAR # noqa: F401,F403

# Do NOT enable db_storage — S3 tests need the real S3 backend.
# S3_HOST et S3_KEY_ID etc. are provided by environment / CI.

FORCE_SCRIPT_NAME = ""
WAGTAILADMIN_BASE_URL = "http://localhost"
