from pathlib import Path

from django.core.management.base import BaseCommand

from sites_conformes.content_manager.services.import_export import ExportPage, ImportExportImages, ImportPages
from sites_conformes.content_manager.utils import get_default_site

SOURCE_URL = "https://sites.beta.gouv.fr/"


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--ids", nargs="+", type=int, help="IDs of the page(s) to migrate, e.g. 5 7")

        parser.add_argument(
            "--site_url", type=str, help=f"[Optional] Root URL of the source site. Default: {SOURCE_URL}"
        )

        parser.add_argument(
            "--parent_page_slug",
            type=str,
            help="[Optional] Slug of the parent page. Defaults to the root page of the default site.",
        )

    def handle(self, *args, **kwargs):
        """
        Download pages from a distant site and clones them locally.
        """

        page_ids = kwargs.get("ids")
        if not page_ids:
            raise ValueError("Missing argument: ids")

        source_site_url = kwargs.get("site_url")
        if not source_site_url:
            source_site_url = SOURCE_URL

        parent_page_slug = kwargs.get("parent_page_slug")
        if not parent_page_slug:
            site = get_default_site()
            parent_page_slug = site.root_page.slug

        image_folder = Path("/tmp/sf_img")
        image_ids = []

        pages = {}

        self.stdout.write(f"Exporting pages from site {source_site_url}.")

        for page_id in page_ids:
            self.stdout.write(f"Exporting page {page_id}")
            page = ExportPage(page_id, source_site_url)
            pages[page_id] = page.json_export
            image_ids += page.image_ids

        image_exporter = ImportExportImages(image_ids, source_site_url, image_folder=image_folder)
        image_exporter.download_images()

        pages_data = {"image_ids": image_ids, "pages": pages}

        page_importer = ImportPages(
            pages_data=pages_data, parent_page_slug=parent_page_slug, image_folder=image_folder
        )
        page_importer.import_pages()
