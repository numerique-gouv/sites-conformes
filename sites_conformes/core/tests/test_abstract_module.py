from django.test import SimpleTestCase

from sites_conformes.core.abstract import AbstractIndexPage, Category, SitesFacilesBasePage, Tag


class SnippetRegistrationTest(SimpleTestCase):
    """Moving a model between modules silently drops its ``@register_snippet``."""

    def test_category_is_registered_as_a_snippet(self):
        self.assertTrue(hasattr(Category, "snippet_viewset"))

    def test_tag_is_registered_as_a_snippet(self):
        self.assertTrue(hasattr(Tag, "snippet_viewset"))


class AbstractModelsTest(SimpleTestCase):
    def test_shared_page_models_are_abstract(self):
        self.assertTrue(AbstractIndexPage._meta.abstract)
        self.assertTrue(SitesFacilesBasePage._meta.abstract)
