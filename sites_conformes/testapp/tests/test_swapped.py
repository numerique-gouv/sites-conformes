from unittest import skipUnless

from django.apps import apps
from django.core.management import call_command
from django.db import connection
from wagtail.models import Site, get_page_models
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core import get_contentpage_model, models as core_models
from sites_conformes.core.models import CatalogIndexPage, ContentPage, Tag
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

    def test_shipped_tag_through_model_is_not_declared(self):
        self.assertFalse(hasattr(core_models, "TagContentPage"))
        self.assertFalse(hasattr(ContentPage, "tags"))
        tables = connection.introspection.table_names()
        self.assertNotIn("sites_conformes_core_contentpage", tables)
        self.assertNotIn("sites_conformes_core_tagcontentpage", tables)

    def test_tags_with_usecount_follows_the_swapped_through_model(self):
        page = self.home.add_child(instance=self.CustomContentPage(title="Tagged", slug="tagged", live=True))
        page.tags.add("dsfr")
        page.save()

        self.assertEqual([tag.name for tag in Tag.objects.tags_with_usecount(1)], ["dsfr"])

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
