import json
from importlib import import_module

from bs4 import BeautifulSoup
from django.apps import apps
from django.db import connection
from django.test import TestCase, override_settings
from wagtail.models import Page, Revision
from wagtail.rich_text import RichText
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.models import ContentPage
from sites_conformes.core.utils import import_image

migration = import_module("sites_conformes.core.migrations.0085_move_centered_image_alt_to_image_block")


def legacy_centered_image(image_id, alt):
    return {
        "title": "",
        "heading_tag": "h3",
        "image": image_id,
        "alt": alt,
        "width": "",
        "image_ratio": "",
        "caption": "",
        "url": "",
    }


class MigrateCenteredImageAltTestCase(TestCase):
    def test_alt_is_moved_to_image_block(self):
        value = legacy_centered_image(12, "Un graphique")

        self.assertTrue(migration.migrate_centered_image_alt(value))

        self.assertNotIn("alt", value)
        self.assertEqual(value["image"], {"image": 12, "decorative": False, "alt_text": "Un graphique"})

    def test_empty_alt_is_removed_and_image_kept_as_id(self):
        value = legacy_centered_image(12, "")

        self.assertTrue(migration.migrate_centered_image_alt(value))

        self.assertNotIn("alt", value)
        self.assertEqual(value["image"], 12)

    def test_existing_image_alt_text_is_kept(self):
        value = legacy_centered_image({"image": 12, "decorative": False, "alt_text": "Déjà saisi"}, "Ancien alt")

        migration.migrate_centered_image_alt(value)

        self.assertEqual(value["image"]["alt_text"], "Déjà saisi")

    def test_nested_values_are_migrated(self):
        stream = [
            {
                "type": "multicolumns",
                "value": {"columns": [{"type": "image", "value": legacy_centered_image(12, "Un graphique")}]},
            }
        ]

        self.assertTrue(migration.migrate_centered_image_alt(stream))

        nested = stream[0]["value"]["columns"][0]["value"]
        self.assertEqual(nested["image"]["alt_text"], "Un graphique")

    def test_other_blocks_are_untouched(self):
        stream = [{"type": "paragraph", "value": "<p>alt</p>"}, {"type": "tile", "value": {"image": 12}}]

        self.assertFalse(migration.migrate_centered_image_alt(stream))


class MigrateCenteredImageAltPagesTestCase(WagtailPageTestCase):
    def setUp(self):
        home = Page.objects.get(slug="home")
        self.image = import_image("sites_conformes/static/artwork/technical-error.svg", "fichier_2023.svg")
        self.page = home.add_child(instance=ContentPage(title="Legacy image", slug="legacy-image"))
        revision = self.page.save_revision()

        # Write the legacy JSON directly, as saving through Wagtail would normalize it
        legacy_body = [{"type": "image", "value": legacy_centered_image(self.image.pk, "Un graphique")}]
        table = ContentPage._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table} SET body = %s WHERE page_ptr_id = %s", [json.dumps(legacy_body), self.page.pk]
            )
        revision.content["body"] = json.dumps(legacy_body)
        revision.save(update_fields=["content"])

    def test_page_and_revision_are_migrated(self):
        self.page.refresh_from_db()
        self.assertIn("alt", self.page.body.raw_data[0]["value"])

        migration.migrate_pages(apps, None)
        migration.migrate_revisions(apps, None)

        self.page.refresh_from_db()
        value = self.page.body.raw_data[0]["value"]
        self.assertNotIn("alt", value)
        self.assertEqual(value["image"]["alt_text"], "Un graphique")
        self.assertFalse(value["image"]["decorative"])

        revision = Revision.objects.filter(object_id=str(self.page.pk)).latest("created_at")
        self.assertNotIn('"alt":', revision.content["body"])
        self.assertIn('"alt_text": "Un graphique"', revision.content["body"])

        response = self.client.get(self.page.url)
        self.assertContains(response, 'alt="Un graphique"')


class DecorativeImagesTestCase(WagtailPageTestCase):
    def setUp(self):
        self.home = Page.objects.get(slug="home")
        self.image = import_image("sites_conformes/static/artwork/technical-error.svg", "fichier_2023.svg")

    def get_soup(self, page):
        return BeautifulSoup(self.client.get(page.url).content, "html.parser")

    def create_page(self, body):
        return self.home.add_child(instance=ContentPage(title="Images", slug="images", body=body))

    def test_quote_image_has_empty_alt(self):
        page = self.create_page([("quote", {"quote": "Citation", "image": self.image})])

        img = self.get_soup(page).select_one(".fr-quote__image img")

        self.assertEqual(img["alt"], "")


class TileImageAltTestCase(WagtailPageTestCase):
    def setUp(self):
        self.home = Page.objects.get(slug="home")
        self.image = import_image("sites_conformes/static/artwork/technical-error.svg", "fichier_2023.svg")

    def create_tile_page(self, alt_text, decorative):
        body = [
            (
                "tile",
                {
                    "title": "Sample tile",
                    "description": RichText("<p>Sample</p>"),
                    "image": {"image": self.image, "alt_text": alt_text, "decorative": decorative},
                },
            )
        ]
        return self.home.add_child(instance=ContentPage(title="Tiles", slug="tiles", body=body))

    def get_soup(self, page):
        return BeautifulSoup(self.client.get(page.url).content, "html.parser")

    def test_tile_image_renders_alt_text(self):
        page = self.create_tile_page("87 % de satisfaction", False)

        img = self.get_soup(page).select_one(".fr-tile__img img")

        self.assertEqual(img["alt"], "87 % de satisfaction")

    def test_decorative_tile_image_has_empty_alt(self):
        page = self.create_tile_page("", True)

        img = self.get_soup(page).select_one(".fr-tile__img img")

        self.assertEqual(img["alt"], "")

    @override_settings(SF_SCHEME_DEPENDENT_SVGS=True)
    def test_tile_svg_pictogram_has_accessible_name(self):
        page = self.create_tile_page("87 % de satisfaction", False)

        svg = self.get_soup(page).select_one(".fr-tile__pictogram svg")

        self.assertEqual(svg["role"], "img")
        self.assertEqual(svg["aria-label"], "87 % de satisfaction")
        self.assertFalse(svg.has_attr("aria-hidden"))

    @override_settings(SF_SCHEME_DEPENDENT_SVGS=True)
    def test_decorative_tile_svg_pictogram_is_hidden(self):
        page = self.create_tile_page("", True)

        svg = self.get_soup(page).select_one(".fr-tile__pictogram svg")

        self.assertEqual(svg["aria-hidden"], "true")
        self.assertFalse(svg.has_attr("role"))
