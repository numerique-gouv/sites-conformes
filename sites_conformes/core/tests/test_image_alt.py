import json
from importlib import import_module

from bs4 import BeautifulSoup
from django.apps import apps
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import translation
from wagtail.models import Locale, Page, Revision
from wagtail.rich_text import RichText
from wagtail.test.utils import WagtailPageTestCase
from wagtail_localize.models import (
    String,
    StringSegment,
    StringTranslation,
    TranslationContext,
    TranslationSource,
)
from wagtail_localize.strings import StringValue

from sites_conformes.core.blocks.utils import HELP_ICON, help_text_with_details
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

    def test_empty_alt_converts_image_to_decorative_image_block(self):
        value = legacy_centered_image(12, "")

        self.assertTrue(migration.migrate_centered_image_alt(value))

        self.assertNotIn("alt", value)
        self.assertEqual(value["image"], {"image": 12, "decorative": True, "alt_text": ""})

    def test_missing_image_is_converted_to_image_block(self):
        value = legacy_centered_image(None, "")

        self.assertTrue(migration.migrate_centered_image_alt(value))

        self.assertEqual(value["image"], {"image": None, "decorative": True, "alt_text": ""})

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

    def test_localize_paths_of_nested_values(self):
        stream = [
            {"type": "image", "id": "a", "value": legacy_centered_image(12, "Un graphique")},
            {
                "type": "multicolumns",
                "id": "b",
                "value": {"columns": [{"type": "image", "id": "c", "value": legacy_centered_image(13, "")}]},
            },
            {"type": "tile", "id": "d", "value": {"image": 12}},
        ]

        self.assertEqual(
            migration.find_legacy_centered_image_paths(stream, ["body"]),
            ["body.a", "body.b.columns.c"],
        )


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

    def test_page_mixing_empty_and_filled_alt_can_be_loaded(self):
        # Wagtail fails to load a stream mixing image IDs and ImageBlock values (e.g. in update_index)
        legacy_body = [
            {"type": "image", "value": legacy_centered_image(self.image.pk, "Un graphique")},
            {"type": "image", "value": legacy_centered_image(self.image.pk, "")},
            {"type": "image", "value": legacy_centered_image(None, "")},
        ]
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {ContentPage._meta.db_table} SET body = %s WHERE page_ptr_id = %s",
                [json.dumps(legacy_body), self.page.pk],
            )

        migration.migrate_pages(apps, None)

        self.page.refresh_from_db()
        *images, missing_image = [block.value["image"] for block in self.page.body]
        self.assertEqual([image.contextual_alt_text for image in images], ["Un graphique", ""])
        self.assertEqual([image.decorative for image in images], [False, True])
        self.assertIsNone(missing_image)

        response = self.client.get(self.page.url)
        imgs = BeautifulSoup(response.content, "html.parser").select("figure img")
        self.assertEqual([img["alt"] for img in imgs], ["Un graphique", ""])

    def test_translation_source_is_migrated(self):
        # Rebuild what wagtail-localize stored before the migration: the legacy content,
        # and the paths of the legacy "alt" and "image" fields, with a translated alt text
        english = Locale.objects.create(language_code="en")
        self.page.get_parent().copy_for_translation(english)
        source, _ = TranslationSource.get_or_create_from_instance(self.page)
        content = json.loads(source.content_json)
        content["body"] = json.dumps(
            [{"type": "image", "id": "block", "value": legacy_centered_image(self.image.pk, "Un graphique")}]
        )
        source.content_json = json.dumps(content)
        source.save()
        source.stringsegment_set.all().delete()
        source.overridablesegment_set.all().delete()
        TranslationContext.objects.filter(object=source.object, path__startswith="body.").delete()
        alt_context = TranslationContext.objects.create(object=source.object, path="body.block.alt")
        TranslationContext.objects.create(object=source.object, path="body.block.image")
        string = String.from_value(self.page.locale, StringValue.from_plaintext("Un graphique"))
        StringSegment.objects.create(source=source, string=string, context=alt_context, order=0, attrs="{}")
        StringTranslation.objects.create(
            translation_of=string, locale=english, context=alt_context, data="A chart", translation_type="manual"
        )

        migration.migrate_translation_sources(apps, None)

        source.refresh_from_db()
        body = json.loads(json.loads(source.content_json)["body"])
        self.assertEqual(body[0]["value"]["image"]["alt_text"], "Un graphique")
        self.assertNotIn("alt", body[0]["value"])
        alt_context.refresh_from_db()
        self.assertEqual(alt_context.path, "body.block.image.alt_text")
        self.assertEqual(alt_context.path_id, TranslationContext._get_path_id("body.block.image.alt_text"))
        self.assertTrue(
            TranslationContext.objects.filter(object=source.object, path="body.block.image.image").exists()
        )

        translated_page, _ = source.create_or_update_translation(english, fallback=True)
        self.assertEqual(translated_page.body[0].value["image"].contextual_alt_text, "A chart")


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


class SectionAndHeroImagesTestCase(WagtailPageTestCase):
    def setUp(self):
        self.home = Page.objects.get(slug="home")
        self.image = import_image("sites_conformes/static/artwork/technical-error.svg", "fichier_2023.svg")
        self.image_value = {"image": self.image, "alt_text": "Un homme dans les nuages", "decorative": False}

    def get_soup(self, page):
        return BeautifulSoup(self.client.get(page.url).content, "html.parser")

    def test_grid_section_keeps_multi_word_alt(self):
        grid_block = ContentPage._meta.get_field("body").stream_block.child_blocks["image_text_grid_section"]
        value = dict(grid_block.get_default())
        value["items"] = [{**dict(item), "image": self.image_value} for item in value["items"]]
        page = self.home.add_child(
            instance=ContentPage(title="Grid", slug="grid", body=[("image_text_grid_section", value)])
        )

        imgs = self.get_soup(page).select(".cmsfr-text-content--left img")

        self.assertTrue(imgs)
        for img in imgs:
            self.assertEqual(img["alt"], "Un homme dans les nuages")

    def test_old_hero_background_is_centered(self):
        hero_block = ContentPage._meta.get_field("hero").stream_block.child_blocks["old_hero"]
        value = {**dict(hero_block.get_default()), "header_image": self.image_value}
        page = self.home.add_child(instance=ContentPage(title="Hero", slug="hero", hero=[("old_hero", value)]))

        hero = self.get_soup(page).select_one(".cmsfr-hero")

        self.assertIn("cmsfr-hero-position--center", hero["class"])


class HelpTextWithDetailsTestCase(TestCase):
    def test_summary_stays_visible_and_details_are_collapsible(self):
        help_text = str(help_text_with_details("Summary", "Details", details_label="Label"))

        self.assertEqual(
            help_text, f'Summary<details class="sf-help-details"><summary>{HELP_ICON}Label</summary>Details</details>'
        )

    def test_default_label_is_translated(self):
        with translation.override("fr"):
            help_text = str(help_text_with_details("Résumé", "Détails"))

        self.assertIn(f"<summary>{HELP_ICON}Comment l'image s'affiche-t-elle ?</summary>", help_text)


@override_settings(SF_SCHEME_DEPENDENT_SVGS=True)
class ImageAndTextSvgAltTestCase(WagtailPageTestCase):
    def setUp(self):
        self.home = Page.objects.get(slug="home")
        self.image = import_image("sites_conformes/static/artwork/technical-error.svg", "fichier_2023.svg")

    def get_svg(self, alt_text, decorative):
        value = {
            "image": {"image": self.image, "alt_text": alt_text, "decorative": decorative},
            "text": RichText("<p>Sample</p>"),
        }
        page = self.home.add_child(
            instance=ContentPage(title="Image and text", slug="image-and-text", body=[("imageandtext", value)])
        )
        soup = BeautifulSoup(self.client.get(page.url).content, "html.parser")
        return soup.select_one(".cmsfr-block-image-and-text svg.fr-artwork")

    def test_svg_artwork_has_accessible_name(self):
        svg = self.get_svg("87 % de satisfaction", False)

        self.assertEqual(svg["role"], "img")
        self.assertEqual(svg["aria-label"], "87 % de satisfaction")
        self.assertFalse(svg.has_attr("aria-hidden"))

    def test_decorative_svg_artwork_is_hidden(self):
        svg = self.get_svg("", True)

        self.assertEqual(svg["aria-hidden"], "true")
        self.assertFalse(svg.has_attr("role"))


class PictureTagTestCase(WagtailPageTestCase):
    def setUp(self):
        self.home = Page.objects.get(slug="home")
        self.image = import_image(
            "sites_conformes/static/illustration/illustration-sites-faciles-homme-nuages.png", "Homme nuages"
        )
        self.image_value = {"image": self.image, "alt_text": "Un homme dans les nuages", "decorative": False}

    def get_soup(self, page):
        return BeautifulSoup(self.client.get(page.url).content, "html.parser")

    def assert_picture(self, picture):
        self.assertEqual([source["type"] for source in picture.select("source")], ["image/avif", "image/webp"])
        self.assertEqual(picture.img["alt"], "Un homme dans les nuages")

    def test_centered_image_keeps_contextual_alt(self):
        value = {"image": self.image_value, "width": "", "image_ratio": ""}
        page = self.home.add_child(instance=ContentPage(title="Image", slug="image", body=[("image", value)]))

        self.assert_picture(self.get_soup(page).select_one(".fr-content-media__img picture"))

    def test_hero_image_keeps_contextual_alt(self):
        hero_block = ContentPage._meta.get_field("hero").stream_block.child_blocks["hero_text_image"]
        value = {**dict(hero_block.get_default()), "image": self.image_value}
        page = self.home.add_child(instance=ContentPage(title="Hero", slug="hero", hero=[("hero_text_image", value)]))

        self.assert_picture(self.get_soup(page).select_one(".fr-col-md-6 picture"))

    def test_grid_section_renders_picture(self):
        grid_block = ContentPage._meta.get_field("body").stream_block.child_blocks["image_text_grid_section"]
        value = dict(grid_block.get_default())
        value["items"] = [{**dict(item), "image": self.image_value} for item in value["items"]]
        page = self.home.add_child(
            instance=ContentPage(title="Grid", slug="grid", body=[("image_text_grid_section", value)])
        )

        pictures = self.get_soup(page).select(".cmsfr-text-content--left picture")

        self.assertTrue(pictures)
        for picture in pictures:
            self.assert_picture(picture)
