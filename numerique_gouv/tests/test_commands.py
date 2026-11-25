from io import StringIO

from django.core.management import call_command
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from numerique_gouv.models import (
    HubPages,
    NumeriqueBlogEntryPage,
    OffersEntryPage,
    PageTag,
    ProductsEntryPage,
    SitemapPage,
)


class CreateE2EPagesTestCase(WagtailPageTestCase):
    def call_command(self):
        call_command("create_e2e_pages", stdout=StringIO())

    def test_creates_renderable_pages(self):
        self.call_command()

        self.assertEqual(NumeriqueBlogEntryPage.objects.live().count(), 4)
        self.assertEqual(OffersEntryPage.objects.live().count(), 4)
        self.assertEqual(ProductsEntryPage.objects.live().count(), 3)

        for slug in ["actualites", "offre-accompagnement", "services-numeriques", "hub-intelligence-artificielle"]:
            with self.subTest(slug=slug):
                page = Page.objects.get(slug=slug).specific
                self.assertPageIsRenderable(page)

        self.assertPageIsRenderable(SitemapPage.objects.get())

    def test_hub_lists_tagged_content(self):
        self.call_command()

        hub = HubPages.objects.get()
        self.assertEqual(len(hub.get_entries("blog")), 2)
        self.assertEqual(len(hub.get_entries("offers")), 2)
        self.assertEqual(len(hub.get_entries("products")), 1)

    def test_is_idempotent(self):
        self.call_command()
        page_count = Page.objects.count()

        self.call_command()

        self.assertEqual(Page.objects.count(), page_count)
        self.assertEqual(PageTag.objects.filter(slug="ia").count(), 1)
