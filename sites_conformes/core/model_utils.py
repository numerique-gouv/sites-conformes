"""
Accessors for swappable page models, following the pattern of
wagtail.images.get_image_model / django.contrib.auth.get_user_model.

These live outside of models.py so they can be imported from anywhere
(services, views, management commands, third-party apps) without
triggering a circular import.
"""

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

DEFAULT_CONTENTPAGE_MODEL = "sites_conformes_core.ContentPage"


def get_contentpage_model_string() -> str:
    """
    Get the dotted ``app_label.ModelName`` for the content page model,
    as a string, usable in foreign keys, ``subpage_types``, etc.
    """
    return getattr(settings, "SF_CONTENTPAGE_MODEL", DEFAULT_CONTENTPAGE_MODEL)


def get_contentpage_model():
    """
    Get the content page model from the ``SF_CONTENTPAGE_MODEL`` setting.
    Defaults to the standard :class:`~sites_conformes.core.models.ContentPage`.
    """
    model_string = get_contentpage_model_string()
    try:
        return apps.get_model(model_string, require_ready=False)
    except ValueError:
        raise ImproperlyConfigured("SF_CONTENTPAGE_MODEL must be of the form 'app_label.model_name'")
    except LookupError:
        raise ImproperlyConfigured(
            f"SF_CONTENTPAGE_MODEL refers to model '{model_string}' that has not been installed"
        )
