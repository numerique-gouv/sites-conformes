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
from typing import cast

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from sites_conformes.env import Csv, config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config("SECRET_KEY", default="")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="127.0.0.1,.localhost", cast=Csv())
USE_X_FORWARDED_HOST = config("USE_X_FORWARDED_HOST", default=False, cast=bool)

HOST_PROTO = config("HOST_PROTO", default="https")
HOST_URL = cast(str, config("HOST_URL", default="localhost"))
HOST_PORT = config("HOST_PORT", default="")

# Prefix of the application when served under a sub-path.
# ``FORCE_SCRIPT_NAME`` is the Django setting handling this behaviour:
# https://docs.djangoproject.com/en/5.2/ref/settings/#force-script-name
FORCE_SCRIPT_NAME = config("FORCE_SCRIPT_NAME", default="").rstrip("/")

# Allow enabling WhiteNoise via an environment variable (disabled by default)
SF_USE_WHITENOISE = config("SF_USE_WHITENOISE", default=False, cast=bool)

# Allow storing media files in PostgreSQL instead of the filesystem (disabled by default)
# Useful for PaaS deployments with ephemeral filesystems (Scalingo, Heroku, etc.)
# /!\ Not recommended beyond 1 GB of media — prefer S3 for larger volumes.
# Selection order: S3_HOST wins if set, then SF_USE_DB_STORAGE, then filesystem (default)
SF_USE_DB_STORAGE = config("SF_USE_DB_STORAGE", default=False, cast=bool)

# Ask search engines not to index anything served by this instance (disabled by default)
SF_NOINDEX = config("SF_NOINDEX", default=False, cast=bool)

# Let browsers and the CDN cache anonymous pages for this many seconds (0 = disabled, default)
SF_PUBLIC_CACHE_MAX_AGE = config("SF_PUBLIC_CACHE_MAX_AGE", default=0, cast=int)

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

DATABASE_URL = config("DATABASE_URL", default="")
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
            "min_length": config("AUTH_PASSWORD_MINIMUM_LENGTH", default=15, cast=int),
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

MEDIA_ROOT = cast(str, config("MEDIA_ROOT", default=""))
S3_HOST = config("S3_HOST", default="")
if S3_HOST:
    protocol = config("S3_PROTOCOL", default="https")
    endpoint_url = f"{protocol}://{S3_HOST}"
    bucket_name = config("S3_BUCKET_NAME", default="")
    public_host = config("S3_PUBLIC_HOST", default="")

    options = {
        "bucket_name": bucket_name,
        "access_key": config("S3_KEY_ID", default=""),
        "secret_key": config("S3_KEY_SECRET", default=""),
        "endpoint_url": endpoint_url,
        "region_name": config("S3_BUCKET_REGION", default="fr"),
        "file_overwrite": False,
        "location": config("S3_LOCATION", default=""),
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
    MEDIA_URL = config("MEDIA_URL", default="db-storage/")
    MEDIA_ROOT = str(BASE_DIR / MEDIA_ROOT)

    if FORCE_SCRIPT_NAME and not MEDIA_URL.startswith(FORCE_SCRIPT_NAME):
        MEDIA_URL = f"{FORCE_SCRIPT_NAME}/{MEDIA_URL}"
else:
    STORAGES["default"] = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    }
    MEDIA_ROOT = str(BASE_DIR / MEDIA_ROOT)
    MEDIA_URL = config("MEDIA_URL", default="medias/")

    if FORCE_SCRIPT_NAME and not MEDIA_URL.startswith(FORCE_SCRIPT_NAME):
        MEDIA_URL = f"{FORCE_SCRIPT_NAME}/{MEDIA_URL}"

# MEDIA_ROOT and STATIC_ROOT must stay strings: dj_static (config/wsgi.py) concatenates them with str paths
STATIC_ROOT = str(BASE_DIR / "staticfiles")

STATIC_URL = config("STATIC_URL", default="static/")

if FORCE_SCRIPT_NAME and not STATIC_URL.startswith(FORCE_SCRIPT_NAME):
    STATIC_URL = f"{FORCE_SCRIPT_NAME}/{STATIC_URL}"


STATICFILES_DIRS = (BASE_DIR / "sites_conformes/static",)

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Wagtail settings
# https://docs.wagtail.org/en/stable/reference/settings.html

WAGTAIL_SITE_NAME = config("SITE_NAME", default="Sites Conformes")

# Base URL to use when referring to full URLs within the Wagtail admin backend -
# e.g. in notification emails. Don't include '/admin' or a trailing slash
WAGTAILADMIN_BASE_URL = config("WAGTAILADMIN_BASE_URL", default="")

# If not set in env, we build it from mandatory variables
if not WAGTAILADMIN_BASE_URL:
    WAGTAILADMIN_BASE_URL = f"{HOST_PROTO}://{HOST_URL}"

    if HOST_PORT:
        WAGTAILADMIN_BASE_URL = f"{WAGTAILADMIN_BASE_URL}:{HOST_PORT}"

WAGTAILAPI_BASE_URL = WAGTAILADMIN_BASE_URL

WAGTAILADMIN_PATH = config("WAGTAILADMIN_PATH", default="cms-admin/")

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
NOTIFICATIONS_FILE_URL = config(
    "NOTIFICATIONS_FILE_URL",
    default="https://raw.githubusercontent.com/numerique-gouv/sites-conformes/refs/heads/main/notifications.json",
)
# GitHub API endpoint used to detect the latest published version (overridable for forks)
LATEST_RELEASE_URL = config(
    "LATEST_RELEASE_URL", default="https://api.github.com/repos/numerique-gouv/sites-conformes/releases/latest"
)
# Human-facing releases page linked from the "new version available" notification (overridable for forks)
RELEASES_URL = config("RELEASES_URL", default="https://github.com/numerique-gouv/sites-conformes/releases")
ADVERTISE_LATEST_VERSION = config("ADVERTISE_LATEST_VERSION", default=True, cast=bool)
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

WAGTAILDOCS_MAX_UPLOAD_SIZE = config("WAGTAILDOCS_MAX_UPLOAD_SIZE", default=10 * 1024 * 1024, cast=int)  # 10MB

WAGTAILIMAGES_IMAGE_MODEL = "sites_conformes_customimages.CustomImage"
WAGTAILIMAGES_EXTENSIONS = ["gif", "jpg", "jpeg", "png", "webp", "svg"]
WAGTAILDOCS_EXTENSIONS = config("WAGTAILDOCS_EXTENSIONS", default="pdf,docx,odt,xlsx,ods,pptx,odp,csv,txt", cast=Csv())
SF_SCHEME_DEPENDENT_SVGS = config("SF_SCHEME_DEPENDENT_SVGS", default=False, cast=bool)

# Allows for complex Streamfields without completely removing checks
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000
DATA_UPLOAD_MAX_MEMORY_SIZE = config("DATA_UPLOAD_MAX_MEMORY_SIZE", default=10 * 1024 * 1024, cast=int)  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = config("FILE_UPLOAD_MAX_MEMORY_SIZE", default=2.5 * 1024 * 1024, cast=int)  # 2.5MB

# Email settings
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="")
if DEFAULT_FROM_EMAIL:
    EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
    EMAIL_HOST = config("EMAIL_HOST", default=None)
    EMAIL_PORT = config("EMAIL_PORT", default=None)
    EMAIL_HOST_USER = config("EMAIL_HOST_USER", default=None)
    EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default=None)
    EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=False, cast=bool)
    EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
    EMAIL_TIMEOUT = config("EMAIL_TIMEOUT", default=30, cast=int)
    EMAIL_SSL_KEYFILE = config("EMAIL_SSL_KEYFILE", default=None)
    EMAIL_SSL_CERTFILE = config("EMAIL_SSL_CERTFILE", default=None)

# Forms
WAGTAIL_PASSWORD_RESET_ENABLED = config("WAGTAIL_PASSWORD_RESET_ENABLED", default=False, cast=bool)
WAGTAILADMIN_USER_PASSWORD_RESET_FORM = "sites_conformes.dashboard.forms.DsfrPasswordResetForm"  # nosec B105
DSFR_MARK_OPTIONAL_FIELDS = config("DSFR_MARK_OPTIONAL_FIELDS", default=True, cast=bool)

# (Optional) 2FA settings
# See https://wagtail-2fa.readthedocs.io/en/stable/
WAGTAIL_2FA_REQUIRED = config("WAGTAIL_2FA_REQUIRED", default=False, cast=bool)
WAGTAIL_2FA_OTP_TOTP_NAME = config("WAGTAIL_2FA_OTP_TOTP_NAME", default=WAGTAIL_SITE_NAME)
# Duration of the confirmation code sent by email to add a 2FA device after a ProConnect login
SF_2FA_EMAIL_CODE_VALIDITY_DURATION = config("SF_2FA_EMAIL_CODE_VALIDITY_DURATION", default=15 * 60, cast=int)
SF_2FA_EMAIL_CODE_MAX_ATTEMPTS = config("SF_2FA_EMAIL_CODE_MAX_ATTEMPTS", default=3, cast=int)

# (Optional) ProConnect settings
PROCONNECT_ACTIVATED = config("PROCONNECT_ACTIVATED", default=False, cast=bool)
OIDC_CREATE_USER = config("PROCONNECT_CREATE_USER", default=True, cast=bool)
OIDC_RP_CLIENT_ID = config("PROCONNECT_CLIENT_ID", default="")
OIDC_RP_CLIENT_SECRET = config("PROCONNECT_CLIENT_SECRET", default="")
OIDC_RP_SCOPES = config("PROCONNECT_SCOPES", default="openid given_name usual_name email siret uid")
OIDC_RP_SIGN_ALGO = config("PROCONNECT_SIGN_ALGO", default="RS256")
OIDC_STORE_ID_TOKEN = True
PROCONNECT_DOMAIN = config("PROCONNECT_DOMAIN", default="fca.integ01.dev-agentconnect.fr")
PROCONNECT_API_ROOT = config("PROCONNECT_API_ROOT", default=f"https://{PROCONNECT_DOMAIN}/api/v2")
OIDC_OP_JWKS_ENDPOINT = f"{PROCONNECT_API_ROOT}/jwks"
OIDC_OP_AUTHORIZATION_ENDPOINT = f"{PROCONNECT_API_ROOT}/authorize"
OIDC_OP_TOKEN_ENDPOINT = f"{PROCONNECT_API_ROOT}/token"
OIDC_OP_USER_ENDPOINT = f"{PROCONNECT_API_ROOT}/userinfo"
OIDC_OP_LOGOUT_ENDPOINT = f"{PROCONNECT_API_ROOT}/session/end"
USER_OIDC_ESSENTIAL_CLAIMS = ["email"]
OIDC_AUTH_REQUEST_EXTRA_PARAMS = {"acr_values": "eidas1"}
OIDC_REDIRECT_ALLOWED_HOSTS = ALLOWED_HOSTS
PROCONNECT_USER_CREATION_FILTER = config("PROCONNECT_USER_CREATION_FILTER", default=None)
LASUITE_DOMAINE_API_KEY = config("LASUITE_DOMAINE_API_KEY", default=None)
SF_DISABLE_LOCAL_LOGIN = config("SF_DISABLE_LOCAL_LOGIN", default=False, cast=bool)

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

CSRF_TRUSTED_ORIGINS += cast(list, config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv()))

# Disable the integrity checksums by default.
# They can clash with Whitenoise and are normally not useful as we serve the statics from a trusted source
DSFR_USE_INTEGRITY_CHECKSUMS = config("DSFR_USE_INTEGRITY_CHECKSUMS", default=False, cast=bool)

SF_DISABLE_TUTORIALS = config("SF_DISABLE_TUTORIALS", default=False, cast=bool)
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Legacy clickjacking fallback for browsers without CSP frame-ancestors
# support. Browsers that support frame-ancestors ignore X-Frame-Options,
# so this does not conflict with the per-site policy emitted by
# sites_conformes.core.middleware.IframeMiddleware.
X_FRAME_OPTIONS = "SAMEORIGIN"

# Sentry config
if sentry_dsn := config("SENTRY_DSN", default=""):
    import sentry_sdk  # noqa: E402

    # Share of requests traced for performance monitoring; tracing is
    # disabled while unset.
    traces_sample_rate = config("SENTRY_TRACES_SAMPLE_RATE", default=0, cast=float)
    if not 0.0 <= traces_sample_rate <= 1.0:
        raise ImproperlyConfigured(f"SENTRY_TRACES_SAMPLE_RATE must be between 0 and 1, got {traces_sample_rate}.")
    sentry_sdk.init(
        dsn=sentry_dsn,
        send_default_pii=config("SENTRY_SEND_DEFAULT_PII", default=False, cast=bool),
        environment=config("SENTRY_ENVIRONMENT", default="production"),
        traces_sample_rate=traces_sample_rate or None,
    )

SENTRY_USE_DEBUG_URL = config("SENTRY_USE_DEBUG_URL", default=False, cast=bool)
