import json

from django.core.management.base import BaseCommand

from sites_conformes.content_manager.services.import_export import TEMPLATES_DATA_FILE, ExportPage, ImportExportImages

SOURCE_URL = "https://sites.beta.gouv.fr/"


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        """
        Export template pages.

        List is manually set for now
        """

        page_ids = ["32", "36", "37", "38", "39", "40", "41", "42", "43", "44"]

        image_ids = []

        pages = {}

        for page_id in page_ids:
            self.stdout.write(f"Exporting page {page_id}")
            page = ExportPage(page_id, SOURCE_URL)
            pages[page_id] = page.json_export
            image_ids += page.image_ids

        image_exporter = ImportExportImages(image_ids, SOURCE_URL)
        image_exporter.download_images()

        export_data = {"image_ids": image_ids, "pages": pages}
        with open(TEMPLATES_DATA_FILE, "w") as json_file:
            json.dump(export_data, json_file, indent=2)
            json_file.write("\n")
