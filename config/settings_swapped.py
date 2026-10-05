"""
Test settings exercising the ``SF_*_MODEL`` settings with the
``sites_conformes.testapp`` reference models. Used by ``just test-swapped``.
"""

from config.settings_test import *  # NOSONAR # noqa: F401,F403

# First, so its migrations are applied before the core ones that depend on the swapped model.
INSTALLED_APPS.insert(0, "sites_conformes.testapp")  # noqa: F405

SF_CONTENTPAGE_MODEL = "sites_conformes_testapp.CustomContentPage"
SF_CATALOGINDEXPAGE_MODEL = "sites_conformes_testapp.CustomCatalogIndexPage"
SF_BLOGINDEXPAGE_MODEL = "sites_conformes_testapp.CustomBlogIndexPage"
SF_BLOGENTRYPAGE_MODEL = "sites_conformes_testapp.CustomBlogEntryPage"
SF_EVENTSINDEXPAGE_MODEL = "sites_conformes_testapp.CustomEventsIndexPage"
SF_EVENTENTRYPAGE_MODEL = "sites_conformes_testapp.CustomEventEntryPage"
SF_FORMPAGE_MODEL = "sites_conformes_testapp.CustomFormPage"
