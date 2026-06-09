import zoneinfo
from datetime import datetime

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from publications.models import Collection, PublicationIndexPage, PublicationPage, Theme

User = get_user_model()


class PublicationPageDisplayTest(WagtailPageTestCase):
    def setUp(self):
        self.home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()
        self.paris_tz = zoneinfo.ZoneInfo("Europe/Paris")

        self.index = self.home.add_child(
            instance=PublicationIndexPage(
                title="Publications",
                slug="publications-index",
                owner=self.admin,
            )
        )
        self.index.save_revision().publish()

        locale = self.index.locale
        self.collection = Collection.objects.create(
            name="Agriculture",
            slug="agriculture",
            locale=locale,
        )
        self.theme = Theme.objects.create(name="Climate", slug="climate", locale=locale)

        self.post = PublicationPage(
            title="Post with taxonomies",
            date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=self.paris_tz),
            owner=self.admin,
        )
        self.index.add_child(instance=self.post)
        self.post.collections.add(self.collection)
        self.post.themes.add(self.theme)
        self.post.save_revision().publish()

    def test_display_collections_and_themes(self):
        response = self.client.get(self.post.url)
        meta_paragraph = next(
            paragraph
            for paragraph in BeautifulSoup(response.content, "html.parser").select("div.fr-container p")
            if "Publié le" in paragraph.get_text()
        )
        collection_link = meta_paragraph.find("a", string=self.collection.name)
        theme_link = meta_paragraph.find("a", string=self.theme.name)
        self.assertIsNotNone(collection_link)
        self.assertIsNotNone(theme_link)
        self.assertIn("collection=agriculture", collection_link["href"])
        self.assertIn("theme=climate", theme_link["href"])
