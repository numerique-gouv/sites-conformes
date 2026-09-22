from django.test import SimpleTestCase

from sites_conformes.core.abstract import AbstractIndexPage, SitesFacilesBasePage
from sites_conformes.core.models import Category, Tag


class AbstractModuleTest(SimpleTestCase):
    def test_abstract_module_only_holds_abstract_page_models(self):
        self.assertTrue(SitesFacilesBasePage._meta.abstract)
        self.assertTrue(AbstractIndexPage._meta.abstract)

    def test_concrete_models_stay_registered_as_snippets(self):
        """Moving a model between modules silently drops its snippet registration."""
        self.assertTrue(hasattr(Category, "snippet_viewset"))
        self.assertTrue(hasattr(Tag, "snippet_viewset"))
