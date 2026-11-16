import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from sites_conformes.core.utils import get_default_site

MIGRATE_PAGES_MODULE = "sites_conformes.core.management.commands.migrate_pages"
EXPORT_TEMPLATES_MODULE = "sites_conformes.core.management.commands.export_page_templates"


def fake_export_page(page_id, source_site):
    """Stand-in for ExportPage that returns the given page ID in its export"""

    class FakeExportPage:
        json_export = {"title": f"Page {page_id}"}
        image_ids = [page_id * 10]

    return FakeExportPage()


@patch(f"{MIGRATE_PAGES_MODULE}.ImportPages")
@patch(f"{MIGRATE_PAGES_MODULE}.ImportExportImages")
@patch(f"{MIGRATE_PAGES_MODULE}.ExportPage", side_effect=fake_export_page)
class MigratePagesCommandTestCase(TestCase):
    def test_ids_are_required(self, mock_export, mock_images, mock_import):
        with self.assertRaisesMessage(ValueError, "Missing argument: ids"):
            call_command("migrate_pages", stdout=StringIO())

        mock_import.assert_not_called()

    def test_pages_are_migrated_with_defaults(self, mock_export, mock_images, mock_import):
        call_command("migrate_pages", "--ids", "5", "7", stdout=StringIO())

        mock_export.assert_any_call(5, "https://sites.beta.gouv.fr/")
        mock_export.assert_any_call(7, "https://sites.beta.gouv.fr/")
        mock_images.assert_called_once_with([50, 70], "https://sites.beta.gouv.fr/", image_folder=Path("/tmp/sf_img"))
        mock_images.return_value.download_images.assert_called_once()

        mock_import.assert_called_once_with(
            pages_data={"image_ids": [50, 70], "pages": {5: {"title": "Page 5"}, 7: {"title": "Page 7"}}},
            parent_page_slug=get_default_site().root_page.slug,
            image_folder=Path("/tmp/sf_img"),
        )
        mock_import.return_value.import_pages.assert_called_once()

    def test_pages_are_migrated_with_options(self, mock_export, mock_images, mock_import):
        call_command(
            "migrate_pages",
            "--ids",
            "5",
            "--site_url",
            "https://source.example.com/",
            "--parent_page_slug",
            "parent",
            stdout=StringIO(),
        )

        mock_export.assert_called_once_with(5, "https://source.example.com/")
        self.assertEqual(mock_import.call_args.kwargs["parent_page_slug"], "parent")


class ExportPageTemplatesCommandTestCase(TestCase):
    @patch(f"{EXPORT_TEMPLATES_MODULE}.ImportExportImages")
    @patch(f"{EXPORT_TEMPLATES_MODULE}.ExportPage")
    def test_templates_are_exported(self, mock_export, mock_images):
        mock_export.return_value.json_export = {"title": "Modèle"}
        mock_export.return_value.image_ids = [1]

        with tempfile.TemporaryDirectory() as tmp_dir:
            data_file = Path(tmp_dir) / "pages_data.json"
            with patch(f"{EXPORT_TEMPLATES_MODULE}.TEMPLATES_DATA_FILE", data_file):
                call_command("export_page_templates", stdout=StringIO())

            export_data = json.loads(data_file.read_text())

        page_ids = ["32", "36", "37", "38", "39", "40", "41", "42", "43", "44"]
        self.assertEqual(list(export_data["pages"].keys()), page_ids)
        self.assertEqual(export_data["pages"]["32"], {"title": "Modèle"})
        self.assertEqual(export_data["image_ids"], [1] * len(page_ids))
        mock_images.assert_called_once_with([1] * len(page_ids), "https://sites.beta.gouv.fr/")
        mock_images.return_value.download_images.assert_called_once()
