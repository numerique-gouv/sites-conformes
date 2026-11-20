from config.settings import *  # NOSONAR # noqa: F401,F403

WHITENOISE_AUTOREFRESH = True
WHITENOISE_MANIFEST_STRICT = False

# Tests must not depend on collectstatic: use plain, unhashed static file URLs
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

FORCE_SCRIPT_NAME = ""
WAGTAILADMIN_BASE_URL = "http://localhost"
