"""
Django settings for sites_conformes project.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.2/ref/settings/

Inspiration
https://github.com/betagouv/tous-a-bord/blob/main/config/settings.py
"""

import sys
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from sites_conformes.env import env, read_env

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

read_env(BASE_DIR / ".env")

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env.str("SECRET_KEY", default="")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", cast=str.strip, default=["127.0.0.1", ".localhost"])
USE_X_FORWARDED_HOST = env.bool("USE_X_FORWARDED_HOST", default=False)

HOST_PROTO = env.str("HOST_PROTO", default="https")
HOST_URL = env.str("HOST_URL", default="localhost")
HOST_PORT = env.str("HOST_PORT", default="")

# Prefix of the application when served under a sub-path.
# ``FORCE_SCRIPT_NAME`` is the Django setting handling this behaviour:
# https://docs.djangoproject.com/en/5.2/ref/settings/#force-script-name
FORCE_SCRIPT_NAME = env.str("FORCE_SCRIPT_NAME", default="").rstrip("/")

# Allow enabling WhiteNoise via an environment variable (disabled by default)
SF_USE_WHITENOISE = env.bool("SF_USE_WHITENOISE", default=False)

# Allow storing media files in PostgreSQL instead of the filesystem (disabled by default)
# Useful for PaaS deployments with ephemeral filesystems (Scalingo, Heroku, etc.)
# /!\ Not recommended beyond 1 GB of media — prefer S3 for larger volumes.
# Selection order: S3_HOST wins if set, then SF_USE_DB_STORAGE, then filesystem (default)
SF_USE_DB_STORAGE = env.bool("SF_USE_DB_STORAGE", default=False)

# Ask search engines not to index anything served by this instance (disabled by default)
SF_NOINDEX = env.bool("SF_NOINDEX", default=False)

# Let browsers and the CDN cache anonymous pages for this many seconds (0 = disabled, default)
SF_PUBLIC_CACHE_MAX_AGE = env.int("SF_PUBLIC_CACHE_MAX_AGE", default=0)

INTERNAL_IPS = [
    "127.0.0.1",
]

# Applications definition

INSTALLED_APPS = [
    # The order is important for overriding templates and using contexts, please change it carefully.
    "storages",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.contrib.routable_page",
    "wagtail.contrib.settings",
    "wagtail.contrib.typed_table_block",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.snippets",
    "wagtail",
    "wagtailmarkdown",
    "wagtailmenus",  # Obsolete, to be removed in a future version (replaced by "sites_conformes.menus")
    "wagtail_localize",
    "wagtail_localize.locales",
    "taggit",
    "wagtail.api.v2",
    "rest_framework",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.humanize",
    "django.contrib.messages",
    "django.contrib.postgres",
    "django.contrib.sessions",
    "django.contrib.sitemaps",
    "django.contrib.staticfiles",
    "widget_tweaks",
    "dsfr",
    "sites_conformes.customimages",
    "sites_conformes.core",
    "sites_conformes.blog",
    "sites_conformes.events",
    "sites_conformes.forms",
    "sites_conformes.menus",
    "wagtail_honeypot",
    "sites_conformes.dashboard",
    "wagtail.admin",
    "wagtail_2fa",
    "django_otp",
    "django_otp.plugins.otp_totp",
]

if SF_USE_DB_STORAGE:
    INSTALLED_APPS.insert(-1, "sites_conformes.db_storage")

if SF_USE_WHITENOISE:
    INSTALLED_APPS.insert(0, "whitenoise.runserver_nostatic")

# Only add these on a dev machine, outside of tests
TESTING = "test" in sys.argv
if not TESTING and DEBUG and "localhost" in HOST_URL:
    INSTALLED_APPS += [
        "wagtail.contrib.styleguide",
        "debug_toolbar",
    ]

# Middleware definition

MIDDLEWARE = [
    # Must stay first so that it also wraps WhiteNoise, inserted below
    "sites_conformes.core.middleware.NoIndexMiddleware",
    # Outside of the session and CSRF middlewares, to see the cookies they set
    "sites_conformes.core.middleware.PublicCacheMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "sites_conformes.dashboard.middleware.VerifyUserStaticFilesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "sites_conformes.core.middleware.IframeMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

if SF_USE_WHITENOISE:
    # Right after SecurityMiddleware, so that static files skip the rest of the stack
    MIDDLEWARE.insert(
        MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
        "whitenoise.middleware.WhiteNoiseMiddleware",
    )

# Only add this on a dev machine, outside of tests
if not TESTING and DEBUG and "localhost" in HOST_URL:
    MIDDLEWARE += [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    ]

    # Don't show the toolbar on admin previews
    def show_toolbar(request):
        request.META["wsgi.multithread"] = True
        request.META["wsgi.multiprocess"] = True
        excluded_urls = [
            "/pages/preview/",
            "/pages/preview_loading/",
            "/edit/",
            "/edit/preview/",
        ]
        excluded = any(request.path.endswith(url) for url in excluded_urls)
        return not excluded

    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": show_toolbar,
    }

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "dsfr/templates",
            BASE_DIR / "sites_conformes/templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "wagtail.contrib.settings.context_processors.settings",
                "wagtailmenus.context_processors.wagtailmenus",
                "sites_conformes.core.context_processors.skiplinks",
                "sites_conformes.core.context_processors.iframe",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
HONEYPOT_ENABLED_DEFAULT = True

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASE_URL = env.str("DATABASE_URL", default="")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    raise ValueError("Please set the DATABASE_URL environment variable")

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": env.int("AUTH_PASSWORD_MINIMUM_LENGTH", default=15),
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "fr"

TIME_ZONE = "Europe/Paris"

USE_I18N = True

USE_TZ = True

WAGTAIL_I18N_ENABLED = True

WAGTAIL_CONTENT_LANGUAGES = LANGUAGES = [
    ("en", "English"),
    ("fr", "Français"),
]

LOCALE_PATHS = [BASE_DIR / "sites_conformes/locale"]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/
STORAGES = {}
STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}

if SF_USE_WHITENOISE:
    if DEBUG:
        STORAGES["staticfiles"] = {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        }
        # Allow WhiteNoise to load files directly from app directories without
        # running ``collectstatic`` each time and reload them on changes.
        WHITENOISE_USE_FINDERS = True
        WHITENOISE_AUTOREFRESH = True
    else:
        STORAGES["staticfiles"] = {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        }

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# S3 uploads & MEDIA CONFIGURATION
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html

MEDIA_ROOT = env.str("MEDIA_ROOT", default="")
S3_HOST = env.str("S3_HOST", default="")
if S3_HOST:
    protocol = env.str("S3_PROTOCOL", default="https")
    endpoint_url = f"{protocol}://{S3_HOST}"
    bucket_name = env.str("S3_BUCKET_NAME", default="")
    public_host = env.str("S3_PUBLIC_HOST", default="")

    options = {
        "bucket_name": bucket_name,
        "access_key": env.str("S3_KEY_ID", default=""),
        "secret_key": env.str("S3_KEY_SECRET", default=""),
        "endpoint_url": endpoint_url,
        "region_name": env.str("S3_BUCKET_REGION", default="fr"),
        "file_overwrite": False,
        "location": env.str("S3_LOCATION", default=""),
    }

    if public_host:
        # Presigned URLs bind the signature to the endpoint hostname, so when the
        # internal endpoint differs from the public one, signing must be disabled.
        # The bucket is appended to custom_domain to produce path-style URLs for MinIO.
        options["custom_domain"] = f"{public_host}/{bucket_name}"
        options["url_protocol"] = f"{protocol}:"
        options["querystring_auth"] = False
        public_endpoint = f"{protocol}://{public_host}"
    else:
        public_endpoint = endpoint_url

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": options,
    }

    MEDIA_URL = f"{public_endpoint}/"
elif SF_USE_DB_STORAGE:
    STORAGES["default"] = {
        "BACKEND": "sites_conformes.db_storage.storage.DatabaseStorage",
    }
    MEDIA_URL = env.str("MEDIA_URL", default="db-storage/")
    MEDIA_ROOT = str(BASE_DIR / MEDIA_ROOT)

    if FORCE_SCRIPT_NAME and not MEDIA_URL.startswith(FORCE_SCRIPT_NAME):
        MEDIA_URL = f"{FORCE_SCRIPT_NAME}/{MEDIA_URL}"
else:
    STORAGES["default"] = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    }
    MEDIA_ROOT = str(BASE_DIR / MEDIA_ROOT)
    MEDIA_URL = env.str("MEDIA_URL", default="medias/")

    if FORCE_SCRIPT_NAME and not MEDIA_URL.startswith(FORCE_SCRIPT_NAME):
        MEDIA_URL = f"{FORCE_SCRIPT_NAME}/{MEDIA_URL}"

# MEDIA_ROOT and STATIC_ROOT must stay strings: dj_static (config/wsgi.py) concatenates them with str paths
STATIC_ROOT = str(BASE_DIR / "staticfiles")

STATIC_URL = env.str("STATIC_URL", default="static/")

if FORCE_SCRIPT_NAME and not STATIC_URL.startswith(FORCE_SCRIPT_NAME):
    STATIC_URL = f"{FORCE_SCRIPT_NAME}/{STATIC_URL}"


STATICFILES_DIRS = (BASE_DIR / "sites_conformes/static",)

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Wagtail settings
# https://docs.wagtail.org/en/stable/reference/settings.html

WAGTAIL_SITE_NAME = env.str("SITE_NAME", default="Sites Conformes")

# Base URL to use when referring to full URLs within the Wagtail admin backend -
# e.g. in notification emails. Don't include '/admin' or a trailing slash
WAGTAILADMIN_BASE_URL = env.str("WAGTAILADMIN_BASE_URL", default="")

# If not set in env, we build it from mandatory variables
if not WAGTAILADMIN_BASE_URL:
    WAGTAILADMIN_BASE_URL = f"{HOST_PROTO}://{HOST_URL}"

    if HOST_PORT:
        WAGTAILADMIN_BASE_URL = f"{WAGTAILADMIN_BASE_URL}:{HOST_PORT}"

WAGTAILAPI_BASE_URL = WAGTAILADMIN_BASE_URL

WAGTAILADMIN_PATH = env.str("WAGTAILADMIN_PATH", default="cms-admin/")

LOGIN_URL = f"{FORCE_SCRIPT_NAME}/{WAGTAILADMIN_PATH}login/"
LOGOUT_URL = f"{FORCE_SCRIPT_NAME}/{WAGTAILADMIN_PATH}logout/"

WAGTAIL_FRONTEND_LOGIN_URL = LOGIN_URL

WAGTAIL_PASSWORD_REQUIRED_TEMPLATE = "sites_conformes_core/password_required.html"  # nosec B105

# Disable Gravatar service
WAGTAIL_GRAVATAR_PROVIDER_URL = None

WAGTAIL_RICHTEXT_FIELD_FEATURES = [
    "h2",
    "h3",
    "h4",
    "bold",
    "italic",
    "link",
    "document-link",
    "image",
    "embed",
    "text-left",
    "text-center",
    "text-right",
]

WAGTAILEMBEDS_RESPONSIVE_HTML = True
WAGTAIL_MODERATION_ENABLED = False

# Settings for the notifications panel of the dashboard admin
NOTIFICATIONS_FILE_URL = env.str(
    "NOTIFICATIONS_FILE_URL",
    default="https://raw.githubusercontent.com/numerique-gouv/sites-conformes/refs/heads/main/notifications.json",
)
# GitHub API endpoint used to detect the latest published version (overridable for forks)
LATEST_RELEASE_URL = env.str(
    "LATEST_RELEASE_URL", default="https://api.github.com/repos/numerique-gouv/sites-conformes/releases/latest"
)
# Human-facing releases page linked from the "new version available" notification (overridable for forks)
RELEASES_URL = env.str("RELEASES_URL", default="https://github.com/numerique-gouv/sites-conformes/releases")
ADVERTISE_LATEST_VERSION = env.bool("ADVERTISE_LATEST_VERSION", default=True)
WAGTAIL_ENABLE_UPDATE_CHECK = False  # Disable Wagtail's own update check, we use our own

# Wagtailmenus: Obsolete, to be removed in a future version (replaced by "sites_conformes.menus")
WAGTAILMENUS_FLAT_MENUS_HANDLE_CHOICES = (
    ("header_tools", "Menu en haut à droite"),
    ("footer", "Menu en pied de page"),
    ("mega_menu_section_1", "Catégorie de méga-menu 1"),
    ("mega_menu_section_2", "Catégorie de méga-menu 2"),
    ("mega_menu_section_3", "Catégorie de méga-menu 3"),
    ("mega_menu_section_4", "Catégorie de méga-menu 4"),
    ("mega_menu_section_5", "Catégorie de méga-menu 5"),
    ("mega_menu_section_6", "Catégorie de méga-menu 6"),
    ("mega_menu_section_7", "Catégorie de méga-menu 7"),
    ("mega_menu_section_8", "Catégorie de méga-menu 8"),
    ("mega_menu_section_9", "Catégorie de méga-menu 9"),
    ("mega_menu_section_10", "Catégorie de méga-menu 10"),
    ("mega_menu_section_11", "Catégorie de méga-menu 11"),
    ("mega_menu_section_12", "Catégorie de méga-menu 12"),
    ("mega_menu_section_13", "Catégorie de méga-menu 13"),
    ("mega_menu_section_14", "Catégorie de méga-menu 14"),
    ("mega_menu_section_15", "Catégorie de méga-menu 15"),
    ("mega_menu_section_16", "Catégorie de méga-menu 16"),
)
WAGTAILMENUS_FLAT_MENUS_EDITABLE_IN_WAGTAILADMIN = False
WAGTAILMENUS_MAIN_MENUS_EDITABLE_IN_WAGTAILADMIN = False

WAGTAILDOCS_MAX_UPLOAD_SIZE = env.int("WAGTAILDOCS_MAX_UPLOAD_SIZE", default=10 * 1024 * 1024)  # 10MB

WAGTAILIMAGES_IMAGE_MODEL = "sites_conformes_customimages.CustomImage"
WAGTAILIMAGES_EXTENSIONS = ["gif", "jpg", "jpeg", "png", "webp", "svg"]
WAGTAILDOCS_EXTENSIONS = env.list(
    "WAGTAILDOCS_EXTENSIONS",
    cast=str.strip,
    default=["pdf", "docx", "odt", "xlsx", "ods", "pptx", "odp", "csv", "txt"],
)
SF_SCHEME_DEPENDENT_SVGS = env.bool("SF_SCHEME_DEPENDENT_SVGS", default=False)

# Allows for complex Streamfields without completely removing checks
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int("DATA_UPLOAD_MAX_MEMORY_SIZE", default=10 * 1024 * 1024)  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = env.int("FILE_UPLOAD_MAX_MEMORY_SIZE", default=int(2.5 * 1024 * 1024))  # 2.5MB

# Email settings
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="")
if DEFAULT_FROM_EMAIL:
    EMAIL_BACKEND = env.str("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
    EMAIL_HOST = env.str("EMAIL_HOST", default=None)
    EMAIL_PORT = env.str("EMAIL_PORT", default=None)
    EMAIL_HOST_USER = env.str("EMAIL_HOST_USER", default=None)
    EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD", default=None)
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
    EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
    EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=30)
    EMAIL_SSL_KEYFILE = env.str("EMAIL_SSL_KEYFILE", default=None)
    EMAIL_SSL_CERTFILE = env.str("EMAIL_SSL_CERTFILE", default=None)

# Forms
WAGTAIL_PASSWORD_RESET_ENABLED = env.bool("WAGTAIL_PASSWORD_RESET_ENABLED", default=False)
WAGTAILADMIN_USER_PASSWORD_RESET_FORM = "sites_conformes.dashboard.forms.DsfrPasswordResetForm"  # nosec B105
DSFR_MARK_OPTIONAL_FIELDS = env.bool("DSFR_MARK_OPTIONAL_FIELDS", default=True)

# (Optional) 2FA settings
# See https://wagtail-2fa.readthedocs.io/en/stable/
WAGTAIL_2FA_REQUIRED = env.bool("WAGTAIL_2FA_REQUIRED", default=False)
WAGTAIL_2FA_OTP_TOTP_NAME = env.str("WAGTAIL_2FA_OTP_TOTP_NAME", default=WAGTAIL_SITE_NAME)
# Duration of the confirmation code sent by email to add a 2FA device after a ProConnect login
SF_2FA_EMAIL_CODE_VALIDITY_DURATION = env.int("SF_2FA_EMAIL_CODE_VALIDITY_DURATION", default=15 * 60)
SF_2FA_EMAIL_CODE_MAX_ATTEMPTS = env.int("SF_2FA_EMAIL_CODE_MAX_ATTEMPTS", default=3)

# (Optional) ProConnect settings
PROCONNECT_ACTIVATED = env.bool("PROCONNECT_ACTIVATED", default=False)
OIDC_CREATE_USER = env.bool("PROCONNECT_CREATE_USER", default=True)
OIDC_RP_CLIENT_ID = env.str("PROCONNECT_CLIENT_ID", default="")
OIDC_RP_CLIENT_SECRET = env.str("PROCONNECT_CLIENT_SECRET", default="")
OIDC_RP_SCOPES = env.str("PROCONNECT_SCOPES", default="openid given_name usual_name email siret uid")
OIDC_RP_SIGN_ALGO = env.str("PROCONNECT_SIGN_ALGO", default="RS256")
OIDC_STORE_ID_TOKEN = True
PROCONNECT_DOMAIN = env.str("PROCONNECT_DOMAIN", default="fca.integ01.dev-agentconnect.fr")
PROCONNECT_API_ROOT = env.str("PROCONNECT_API_ROOT", default=f"https://{PROCONNECT_DOMAIN}/api/v2")
OIDC_OP_JWKS_ENDPOINT = f"{PROCONNECT_API_ROOT}/jwks"
OIDC_OP_AUTHORIZATION_ENDPOINT = f"{PROCONNECT_API_ROOT}/authorize"
OIDC_OP_TOKEN_ENDPOINT = f"{PROCONNECT_API_ROOT}/token"
OIDC_OP_USER_ENDPOINT = f"{PROCONNECT_API_ROOT}/userinfo"
OIDC_OP_LOGOUT_ENDPOINT = f"{PROCONNECT_API_ROOT}/session/end"
USER_OIDC_ESSENTIAL_CLAIMS = ["email"]
OIDC_AUTH_REQUEST_EXTRA_PARAMS = {"acr_values": "eidas1"}
OIDC_REDIRECT_ALLOWED_HOSTS = ALLOWED_HOSTS
PROCONNECT_USER_CREATION_FILTER = env.str("PROCONNECT_USER_CREATION_FILTER", default=None)
LASUITE_DOMAINE_API_KEY = env.str("LASUITE_DOMAINE_API_KEY", default=None)
SF_DISABLE_LOCAL_LOGIN = env.bool("SF_DISABLE_LOCAL_LOGIN", default=False)

LOGIN_REDIRECT_URL = f"{FORCE_SCRIPT_NAME}/"
LOGOUT_REDIRECT_URL = f"{FORCE_SCRIPT_NAME}/"

if PROCONNECT_ACTIVATED:
    INSTALLED_APPS += [
        "mozilla_django_oidc",
        "sites_conformes.proconnect",
    ]

    if SF_DISABLE_LOCAL_LOGIN:
        AUTHENTICATION_BACKENDS = []
        WAGTAIL_PASSWORD_RESET_ENABLED = False
        WAGTAIL_PASSWORD_MANAGEMENT_ENABLED = False
        WAGTAILUSERS_PASSWORD_ENABLED = False
    else:
        AUTHENTICATION_BACKENDS = [
            "django.contrib.auth.backends.ModelBackend",
        ]

    AUTHENTICATION_BACKENDS.append("sites_conformes.proconnect.backends.OIDCAuthenticationBackend")

    LOGOUT_URL = f"{FORCE_SCRIPT_NAME}/oidc/logout/"

# CSRF
CSRF_FAILURE_VIEW = "sites_conformes.core.views.csrf_failure"
CSRF_TRUSTED_ORIGINS = []
for host in ALLOWED_HOSTS:
    if host not in ["127.0.0.1", "localhost", ".localhost"]:
        if HOST_PORT:
            CSRF_TRUSTED_ORIGINS.append(f"{HOST_PROTO}://{host}:{HOST_PORT}")
        else:
            CSRF_TRUSTED_ORIGINS.append(f"{HOST_PROTO}://{host}")

CSRF_TRUSTED_ORIGINS += [origin for origin in env.list("CSRF_TRUSTED_ORIGINS", cast=str.strip, default=[]) if origin]

# Disable the integrity checksums by default.
# They can clash with Whitenoise and are normally not useful as we serve the statics from a trusted source
DSFR_USE_INTEGRITY_CHECKSUMS = env.bool("DSFR_USE_INTEGRITY_CHECKSUMS", default=False)

SF_DISABLE_TUTORIALS = env.bool("SF_DISABLE_TUTORIALS", default=False)
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Legacy clickjacking fallback for browsers without CSP frame-ancestors
# support. Browsers that support frame-ancestors ignore X-Frame-Options,
# so this does not conflict with the per-site policy emitted by
# sites_conformes.core.middleware.IframeMiddleware.
X_FRAME_OPTIONS = "SAMEORIGIN"

# Sentry config
if sentry_dsn := env.str("SENTRY_DSN", default=""):
    import sentry_sdk  # noqa: E402

    # Share of requests traced for performance monitoring; tracing is
    # disabled while unset.
    traces_sample_rate = env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0)
    if not 0.0 <= traces_sample_rate <= 1.0:
        raise ImproperlyConfigured(f"SENTRY_TRACES_SAMPLE_RATE must be between 0 and 1, got {traces_sample_rate}.")
    sentry_sdk.init(
        dsn=sentry_dsn,
        send_default_pii=env.bool("SENTRY_SEND_DEFAULT_PII", default=False),
        environment=env.str("SENTRY_ENVIRONMENT", default="production"),
        traces_sample_rate=traces_sample_rate or None,
    )

SENTRY_USE_DEBUG_URL = env.bool("SENTRY_USE_DEBUG_URL", default=False)
