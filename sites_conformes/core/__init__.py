"""
Accessors for the swappable page models (settings ``SF_*_MODEL``),
in the manner of ``django.contrib.auth.get_user_model``.

They live here, without importing any model, so they can be used from models,
migrations, views and management commands alike.
"""

# Aliased: the ``sites_conformes.core.apps`` submodule would shadow a bare ``apps`` name.
from django.apps import apps as django_apps
from django.conf import settings

# Setting name -> shipped model
SWAPPABLE_MODELS = {
    "SF_CONTENTPAGE_MODEL": "sites_conformes_core.ContentPage",
    "SF_CATALOGINDEXPAGE_MODEL": "sites_conformes_core.CatalogIndexPage",
    "SF_BLOGINDEXPAGE_MODEL": "sites_conformes_blog.BlogIndexPage",
    "SF_BLOGENTRYPAGE_MODEL": "sites_conformes_blog.BlogEntryPage",
    "SF_EVENTSINDEXPAGE_MODEL": "sites_conformes_events.EventsIndexPage",
    "SF_EVENTENTRYPAGE_MODEL": "sites_conformes_events.EventEntryPage",
    "SF_FORMPAGE_MODEL": "sites_conformes_forms.FormPage",
}

DEFAULT_CONTENTPAGE_MODEL = SWAPPABLE_MODELS["SF_CONTENTPAGE_MODEL"]


def get_model_string(setting: str) -> str:
    """
    Return the ``app_label.ModelName`` string of the model set by ``setting`` (one of ``SWAPPABLE_MODELS``),
    for use in foreign keys, ``subpage_types`` and migrations.
    """
    return getattr(settings, setting, SWAPPABLE_MODELS[setting])


def is_model_swapped(setting: str) -> bool:
    """
    Return whether ``setting`` points at another model than the shipped one
    (the same comparison as ``Model._meta.swapped``, usable before models are loaded).
    """
    return get_model_string(setting).lower() != SWAPPABLE_MODELS[setting].lower()


def get_model(setting: str):
    """
    Return the model class set by ``setting``. Only valid once the app registry is ready.
    """
    return django_apps.get_model(get_model_string(setting))


def get_contentpage_model_string() -> str:
    return get_model_string("SF_CONTENTPAGE_MODEL")


def is_contentpage_swapped() -> bool:
    return is_model_swapped("SF_CONTENTPAGE_MODEL")


def get_contentpage_model():
    return get_model("SF_CONTENTPAGE_MODEL")


def without_swapped_relations(operations: list, setting: str, through_models: tuple, fields: tuple = ()) -> list:
    """
    Migration operations for a project that swapped the model of ``setting`` out: drop the operations
    on its ``through_models`` and on its ``fields`` towards them, which the project declares on its own model.
    Returns the operations untouched when the shipped model is in use.
    """
    if not is_model_swapped(setting):
        return operations

    page = SWAPPABLE_MODELS[setting].split(".")[1].lower()
    kept = []
    for operation in operations:
        # CreateModel and the like name their model ``name``; field operations ``model_name`` (and the field ``name``)
        model = getattr(operation, "model_name", None)
        name = getattr(operation, "name", "")
        if model is None:
            if name.lower() in through_models:
                continue
            if name.lower() == page and hasattr(operation, "fields"):
                operation.fields = [field for field in operation.fields if field[0] not in fields]
        elif model.lower() in through_models or (model.lower() == page and name in fields):
            continue
        kept.append(operation)
    return kept
