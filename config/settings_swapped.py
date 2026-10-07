"""
Test settings exercising the ``SF_CONTENTPAGE_MODEL`` setting with the
``sites_conformes.testapp`` reference model. Used by ``just test-swapped``.
"""

from config.settings_test import *  # NOSONAR # noqa: F401,F403

INSTALLED_APPS.append("sites_conformes.testapp")  # noqa: F405

SF_CONTENTPAGE_MODEL = "sites_conformes_testapp.CustomContentPage"
