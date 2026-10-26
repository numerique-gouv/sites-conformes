import copy
import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.models import ContentPage
from sites_conformes.core.services.import_export import (
    ExportPage,
    ImportExportImages,
    ImportPages,
    remove_block_ids,
    update_streamfield_image_ids,
)


class ImportPagesTestCase(WagtailPageTestCase):
    def setUp(self):
        call_command("create_starter_pages")
        call_command("import_page_templates")
        self.templates_index = ContentPage.objects.get(slug="page_templates_index")
        self.home_page = ContentPage.objects.get(slug="home")

    def test_copied_template_is_correctly_updated(self):
        template = ContentPage.objects.child_of(self.templates_index).first()
        new_page = template.copy(to=self.home_page)

        self.assertEqual(new_page.get_parent(), self.home_page)
        self.assertEqual(new_page.source_url, None)

        find_template = (
            ContentPage.objects.child_of(self.templates_index).filter(source_url=template.source_url).first()
        )
        self.assertEqual(template.id, find_template.id)


def page_api_response():
    """Minimal copy of a page as returned by the Wagtail API of the source site"""
    return {
        "id": 32,
        "meta": {
            "type": "sites_conformes_core.ContentPage",
            "html_url": "https://source.example.com/modele/",
            "slug": "modele",
            "parent": {"id": 1},
            "seo_title": "SEO",
            "search_description": "Description",
        },
        "title": "Modèle",
        "body": [
            {"type": "paragraph", "value": "<p>Bonjour</p>", "id": "block-1"},
            {
                "type": "imageandtext",
                "id": "block-2",
                "value": {"image": 7, "text": "<p>Texte</p>", "items": [{"bg_image": {"image": 8}, "id": "x"}]},
            },
            {"type": "image", "id": "block-3", "value": {"image": 7}},
        ],
        "tags": ["tag"],
        "header_image": {"id": 5, "meta": {"download_url": "https://source.example.com/media/header.png"}},
        "header_image_render": {"url": "render"},
        "header_image_thumbnail": {"url": "thumbnail"},
    }


class StreamfieldHelpersTestCase(SimpleTestCase):
    def test_remove_block_ids(self):
        value = [{"id": "a", "type": "paragraph", "value": {"id": "b", "items": [{"id": "c", "text": "t"}]}}, 3]

        self.assertEqual(
            remove_block_ids(value),
            [{"type": "paragraph", "value": {"items": [{"text": "t"}]}}, 3],
        )

    def test_update_streamfield_image_ids(self):
        image_data = {"7": {"local_id": 70}, "8": {"local_id": 80}}
        value = [{"type": "image", "value": {"image": 7}}, {"value": {"bg_image": 8, "other": 7}}, {"image": 9}]

        self.assertEqual(
            update_streamfield_image_ids(value, image_data),
            [{"type": "image", "value": {"image": 70}}, {"value": {"bg_image": 80, "other": 7}}, {"image": 9}],
        )


class ExportPageTestCase(TestCase):
    @patch("sites_conformes.core.services.import_export.requests.get")
    def test_export_page(self, mock_get):
        mock_get.return_value.json.return_value = page_api_response()

        export = ExportPage(32, "https://source.example.com/")

        mock_get.assert_called_once_with("https://source.example.com/api/v2/pages/32/", timeout=5)
        content = export.json_export
        self.assertEqual(content["title"], "Modèle")
        self.assertNotIn("id", content["body"][0])
        self.assertNotIn("id", content["body"][1]["value"]["items"][0])
        for key in ["tags", "header_image_render", "header_image_thumbnail"]:
            self.assertNotIn(key, content)
        for key in ["parent", "seo_title", "search_description"]:
            self.assertNotIn(key, content["meta"])
        self.assertEqual(content["meta"]["slug"], "modele")
        self.assertNotIn("download_url", content["header_image"]["meta"])

        # Header image, body images (plain and with alt) and no duplicate
        self.assertEqual(sorted(export.image_ids), [5, 7, 8])


class ImportExportImagesTestCase(TestCase):
    def setUp(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        self.image_folder = Path(tmp_dir.name)

    @patch("sites_conformes.core.services.import_export.requests.get")
    def test_download_images(self, mock_get):
        api_responses = {
            "https://source.example.com/api/v2/images/1/": {
                "title": "Photo",
                "meta": {"download_url": "https://source.example.com/media/photo.png?v=1"},
            },
            "https://source.example.com/api/v2/images/2/": {
                "title": "Pictogramme",
                "meta": {"download_url": "https://source.example.com/media/Pictogrammes_DSFR__Digital_Mail.svg"},
            },
        }

        def fake_get(url, **kwargs):
            response = MagicMock()
            if kwargs.get("stream"):
                response.__enter__.return_value.iter_content.return_value = [b"PNG", b"DATA"]
            else:
                response.json.return_value = copy.deepcopy(api_responses[url])
            return response

        mock_get.side_effect = fake_get

        exporter = ImportExportImages([1, 2, 1], "https://source.example.com/", image_folder=self.image_folder)
        self.assertEqual(exporter.image_data, {})
        exporter.download_images()

        self.assertEqual((self.image_folder / "photo.png").read_bytes(), b"PNGDATA")
        self.assertEqual(len([c for c in mock_get.call_args_list if c.kwargs.get("stream")]), 1)

        image_data = json.loads((self.image_folder / "image_data.json").read_text())
        self.assertEqual(image_data["1"]["filename"], "photo.png")
        self.assertFalse(image_data["1"]["is_pictogram"])
        self.assertEqual(image_data["1"]["title"], "Photo")
        self.assertNotIn("download_url", image_data["1"]["meta"])
        self.assertEqual(image_data["2"]["filename"], "Pictogrammes DSFR — Digital Mail.svg")
        self.assertTrue(image_data["2"]["is_pictogram"])

        # The saved data is reloaded by a new instance
        reloaded = ImportExportImages([1], image_folder=self.image_folder)
        self.assertEqual(reloaded.image_data, image_data)


class ImportPagesWithParentTestCase(WagtailPageTestCase):
    def setUp(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        self.image_folder = Path(tmp_dir.name)

        home = Page.objects.get(slug="home")
        self.parent = home.add_child(instance=ContentPage(title="Parent", slug="parent"))

    def pages_data(self, title):
        page = {
            "meta": {"html_url": "https://source.example.com/modele/", "slug": "modele"},
            "title": title,
            "body": [{"type": "paragraph", "value": "<p>Bonjour</p>"}],
            "header_image": None,
            "header_with_title": True,
            "header_color_class": None,
            "header_large": False,
            "header_darken": False,
            "header_cta_text": "",
            "header_cta_buttons": [],
        }
        return {"image_ids": [], "pages": {"32": page}}

    def import_pages(self, title):
        importer = ImportPages(
            pages_data=self.pages_data(title), parent_page_slug="parent", image_folder=self.image_folder
        )
        with redirect_stdout(StringIO()):
            importer.import_pages()

    def test_pages_are_imported_then_updated(self):
        self.import_pages("Modèle")

        page = ContentPage.objects.child_of(self.parent).get()
        self.assertEqual(page.title, "Modèle")
        self.assertEqual(page.source_url, "https://source.example.com/modele/")
        self.assertTrue(page.header_with_title)

        self.import_pages("Modèle mis à jour")

        updated_page = ContentPage.objects.child_of(self.parent).get()
        self.assertEqual(updated_page.pk, page.pk)
        self.assertEqual(updated_page.title, "Modèle mis à jour")
        self.assertFalse(ContentPage.objects.filter(slug="page_templates_index").exists())
