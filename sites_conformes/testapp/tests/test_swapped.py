from unittest import skipUnless

from django.apps import apps
from django.core.management import call_command
from wagtail.models import Site, get_page_models
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core import get_contentpage_model
from sites_conformes.core.models import CatalogIndexPage, ContentPage
from sites_conformes.core.services.accessors import get_or_create_content_page


@skipUnless(apps.is_installed("sites_conformes.testapp"), "requires config.settings_swapped")
class SwappedContentPageTestCase(WagtailPageTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.CustomContentPage = get_contentpage_model()
        cls.home = Site.objects.get(is_default_site=True).root_page

    def test_setting_swaps_the_model(self):
        from sites_conformes.testapp.models import CustomContentPage

        self.assertIs(self.CustomContentPage, CustomContentPage)
        self.assertEqual(ContentPage._meta.swapped, "sites_conformes_testapp.CustomContentPage")

    def test_default_model_is_hidden_from_wagtail(self):
        self.assertNotIn(ContentPage, get_page_models())
        self.assertIn(self.CustomContentPage, get_page_models())
        self.assertCanCreateAt(CatalogIndexPage, self.CustomContentPage)
        self.assertCanNotCreateAt(CatalogIndexPage, ContentPage)

    def test_create_tag_and_render(self):
        page = self.home.add_child(instance=self.CustomContentPage(title="Custom", slug="custom", subtitle="sub"))
        page.tags.add("dsfr")
        page.save()

        self.assertEqual(list(self.CustomContentPage.objects.filter(tags__name="dsfr")), [page])
        self.assertPageIsRenderable(page)

    def test_catalog_lists_custom_pages(self):
        catalog = self.home.add_child(instance=CatalogIndexPage(title="Catalogue", slug="catalogue"))
        child = catalog.add_child(instance=self.CustomContentPage(title="Entry", slug="entry", live=True))

        self.assertEqual(list(catalog.entries), [child])

    def test_accessor_creates_the_swapped_model(self):
        page = get_or_create_content_page(slug="via-accessor", title="Via accessor", body=[])
        self.assertIsInstance(page, self.CustomContentPage)

    def test_starter_pages_command_uses_the_swapped_model(self):
        call_command("create_starter_pages", verbosity=0)
        self.assertTrue(self.CustomContentPage.objects.filter(slug="home").exists())
