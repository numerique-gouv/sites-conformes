from config.settings import *  # NOSONAR # noqa: F401,F403

# Enable db_storage for testing its functionality
SF_USE_DB_STORAGE = True
if "db_storage" not in INSTALLED_APPS:  # noqa: F405
    INSTALLED_APPS.insert(-1, "db_storage")  # noqa: F405

WHITENOISE_AUTOREFRESH = True
WHITENOISE_MANIFEST_STRICT = False

FORCE_SCRIPT_NAME = ""
WAGTAILADMIN_BASE_URL = "http://localhost"
