"""
Accessors for the swappable content page model (setting ``SF_CONTENTPAGE_MODEL``),
in the manner of ``django.contrib.auth.get_user_model``.

They live here, without importing any model, so they can be used from models,
migrations, views and management commands alike.
"""

# Aliased: the ``sites_conformes.core.apps`` submodule would shadow a bare ``apps`` name.
from django.apps import apps as django_apps
from django.conf import settings

DEFAULT_CONTENTPAGE_MODEL = "sites_conformes_core.ContentPage"


def get_contentpage_model_string() -> str:
    """
    Return the ``app_label.ModelName`` string of the content page model,
    for use in foreign keys, ``subpage_types`` and migrations.
    """
    return getattr(settings, "SF_CONTENTPAGE_MODEL", DEFAULT_CONTENTPAGE_MODEL)


def get_contentpage_model():
    """
    Return the content page model class. Only valid once the app registry is ready.
    """
    return django_apps.get_model(get_contentpage_model_string())
