"""
Import and export of pages and images between Wagtail instances, through the API (`api/v2/`).

Used by the `migrate_pages` command (copy pages from another site), and by the
`export_page_templates` / `import_page_templates` commands, which store the page
templates in `PAGE_TEMPLATES_ROOT` (pages in `pages_data.json`, images in `img/`).
"""

import copy
import json
import os
import sys
from io import BytesIO
from pathlib import PosixPath

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.images import ImageFile
from django.utils import timezone
from wagtail.images import get_image_model
from wagtail.models import Page
from wagtail.utils.file import hash_filelike

from sites_conformes.core.constants import HEADER_FIELDS
from sites_conformes.core.models import ContentPage
from sites_conformes.core.services.accessors import get_or_create_collection, get_or_create_content_page

PAGE_TEMPLATES_ROOT = settings.BASE_DIR / "sites_conformes/core/page_templates"
TEMPLATES_DATA_FILE = PAGE_TEMPLATES_ROOT / "pages_data.json"
IMAGES_FOLDER = PAGE_TEMPLATES_ROOT / "img"

User = get_user_model()
Image = get_image_model()


class ExportPage:
    """
    Generic class for export of a ContentPage from a wagtail instance

    The page is fetched from the API of `source_site` (a base URL ending with a slash)
    when the class is instantiated. The block IDs, the tags, the rendered header images
    and some meta keys are removed, and the IDs of the images used by the page are
    listed in `image_ids`, so that they can be exported with `ImportExportImages`.
    """

    def __init__(self, source_page_id, source_site) -> None:
        self.source_site = source_site
        self.source_page_id = source_page_id
        self.source_content = self.get_content_from_source_page()
        self.source_body = self.source_content["body"]
        self.user = User.objects.filter(is_superuser=True).first()

        self.content = copy.deepcopy(self.source_content)
        self.content["body"] = remove_block_ids(self.source_body)
        self.content.pop("tags", None)
        self.content.pop("header_image_render", None)
        self.content.pop("header_image_thumbnail", None)
        self.clear_meta_keys()

        self.images = {}
        self.image_ids = []
        self.get_source_images()

    @property
    def json_export(self) -> dict:
        """
        The cleaned page content, ready to be imported with `ImportPages`.
        """
        return self.content

    @property
    def source_page_api_url(self):
        """
        The URL of the page in the API of the source site.
        """
        return f"{self.source_site}api/v2/pages/{self.source_page_id}/"

    def get_content_from_source_page(self):
        """
        Fetch the page from the API of the source site and return its JSON content.
        """
        response = requests.get(self.source_page_api_url, timeout=5)
        return response.json()

    def get_source_images(self) -> None:
        """
        Get a list of images present in the source content.

        Fills `image_ids` with the IDs of the header image and of the images of the body,
        without duplicates.
        """

        # Header image
        header_image = self.source_content.get("header_image", None)
        if header_image:
            header_image["local_image"] = None
            self.image_ids.append(header_image["id"])
            self.content["header_image"]["meta"].pop("download_url")

        # Images from the body
        self.locate_image_ids(self.source_body)
        self.image_ids = list(set(self.image_ids))

    def locate_image_ids(self, json_object):  # NOSONAR
        """
        Recursively walk a StreamField JSON representation and add to `image_ids`
        the values of the `image` and `bg_image` keys.
        """
        if isinstance(json_object, dict) and json_object:
            for key, value in json_object.items():
                if key in ["image", "bg_image"] and value:
                    # Manage the case of images with alt
                    if isinstance(value, dict):
                        self.image_ids.append(value["image"])
                    else:
                        self.image_ids.append(value)
                else:
                    self.locate_image_ids(value)

        elif isinstance(json_object, list) and json_object:
            for item in json_object:
                self.locate_image_ids(item)

    def clear_meta_keys(self):
        """
        Remove the meta keys that should not be copied to the imported page.
        """
        keys = ["parent", "seo_title", "search_description"]
        for key in keys:
            self.content["meta"].pop(key, None)


class ImportPages:
    """
    Generic class for import of a list of ContentPages from a previously made export

    `pages_data` is a dict with a `pages` key (the exported pages, by source page ID)
    and an `image_ids` key. It defaults to the content of `TEMPLATES_DATA_FILE`.
    The pages are imported under the page whose slug is `parent_page_slug`, or under
    a page templates index created right under the Root page.
    """

    def __init__(
        self,
        pages_data: dict | None = None,
        parent_page_slug: str | None = None,
        image_folder: PosixPath | None = IMAGES_FOLDER,
    ) -> None:
        if pages_data is None:
            with open(TEMPLATES_DATA_FILE, "r") as json_file:
                pages_data = json.load(json_file)

        self.pages = pages_data["pages"]  # type: ignore
        self.image_ids = pages_data["image_ids"]  # type: ignore

        self.image_importer = ImportExportImages(self.image_ids, image_folder=image_folder)

        if parent_page_slug:
            self.parent_page = ContentPage.objects.get(slug=parent_page_slug)
        else:
            # Do not create the parent page at this step if it doesn't exit
            self.parent_page = None

    def get_or_create_page_templates_index(self) -> ContentPage:
        """
        Get or create the page templates index, used as parent page when none is given.
        """
        # The templates index is created right under the Root page, like a site
        parent_page = Page.objects.first()
        body = [("subpageslist", None)]
        return get_or_create_content_page(
            slug="page_templates_index", title="Modèles de pages à copier", body=body, parent_page=parent_page
        )

    def import_pages(self):
        """
        Import the images, then the pages.

        A page that was already imported under the parent page (same `source_url`)
        is updated instead of being duplicated.
        """
        self.image_importer.import_images()

        if not self.parent_page:
            self.parent_page = self.get_or_create_page_templates_index()

        for page_id in self.pages.keys():
            self.update_image_ids(page_id)

            raw_page = self.pages[page_id]
            source_url = raw_page["meta"]["html_url"]

            page_exists = ContentPage.objects.child_of(self.parent_page).filter(source_url=source_url).first()
            if page_exists:
                self.update_page(page_id, page_exists)
            else:
                self.import_page(page_id)

    def import_page(self, page_id: str) -> ContentPage:
        """
        Create a new page from the exported page with the given source ID.
        """
        raw_page = self.pages[page_id]
        source_url = raw_page["meta"]["html_url"]

        page_dict = {
            "slug": raw_page["meta"]["slug"],
            "title": raw_page["title"],
            "body": raw_page["body"],
            "parent_page": self.parent_page,
        }

        page_fields = {"source_url": source_url}

        for field in HEADER_FIELDS:
            if raw_page[field]:
                page_fields[field] = raw_page[field]
        page_dict["page_fields"] = page_fields
        return get_or_create_content_page(**page_dict)

    def update_page(self, source_page_id, existing_page):
        """
        Update an existing page (slug, title, body and header fields)
        with the content of the exported page with the given source ID.
        """
        raw_page = self.pages[source_page_id]
        existing_page.slug = raw_page["meta"]["slug"]
        existing_page.title = raw_page["title"]
        existing_page.body = raw_page["body"]

        for field in HEADER_FIELDS:
            if raw_page[field]:
                setattr(existing_page, field, raw_page[field])

        existing_page.save()
        sys.stdout.write(f"Page {existing_page.slug} has been updated.\n")
        return existing_page

    def update_image_ids(self, page_id):
        """
        Replace the source image IDs of the exported page with the IDs of the imported images.
        """
        page = self.pages[page_id]

        if page["header_image"]:
            source_image_id = str(page["header_image"]["id"])
            local_image_id = self.image_importer.image_data[source_image_id]["local_id"]

            # We need to replace the dictionary with the image itself
            page["header_image"] = Image.objects.get(pk=local_image_id)

        page["body"] = update_streamfield_image_ids(page["body"], self.image_importer.image_data)


class ImportExportImages:
    """
    Generic class for import/export of a list of Images from a wagtail instance

    `image_folder` holds the image files and an `image_data.json` file with their metadata.
    `source_site` (a base URL ending with a slash) is only needed to download images.

    When instantiated, the class creates `image_folder` and the
    "Images des modèles de page" collection if they don't exist.
    """

    def __init__(self, image_ids, source_site=None, image_folder: PosixPath | None = IMAGES_FOLDER) -> None:
        self.user = User.objects.filter(is_superuser=True).first()

        self.image_ids = set(image_ids)
        self.source_site = source_site

        # Create the folder for the files if it doesn't exist
        self.image_folder = image_folder
        os.makedirs(image_folder, exist_ok=True)

        self.image_data_file = self.image_folder / "image_data.json"  # type: ignore

        # Create the collection if it doesn't exit
        self.collection = get_or_create_collection("Images des modèles de page")

        self.image_data = self.get_image_data()

    def get_image_data(self) -> dict:
        """
        Return the content of `image_data.json`, or an empty dict if the file doesn't exist.
        """
        if os.path.isfile(self.image_data_file):
            with open(self.image_data_file, "r") as json_file:
                image_data = json.load(json_file)
        else:
            image_data = {}

        return image_data

    def source_image_api_url(self, image_id: int) -> str:
        """
        Return the URL of the image in the API of the source site.
        """
        return f"{self.source_site}api/v2/images/{image_id}/"

    def get_content_from_source_image(self, image_id: int) -> dict:
        """
        Fetch the image from the API of the source site and return its JSON content.
        """
        response = requests.get(self.source_image_api_url(image_id), timeout=5)
        return response.json()

    def download_images(self) -> None:
        """
        Download the images from the source site to `image_folder`, and save their metadata
        in `image_data.json`.

        The DSFR pictograms are not downloaded, as they should already be present
        on the target site: they are found again by their title when imported.
        """
        for i in self.image_ids:
            i = str(i)
            image = self.get_content_from_source_image(i)

            if i not in self.image_data:
                self.image_data[i] = {}
            self.image_data[i]["meta"] = image["meta"]
            self.image_data[i]["title"] = image["title"]

            image_url = image["meta"].pop("download_url")
            image_name = image_url.split("?")[0].split("/")[-1]

            # No need to export the pictograms, as they should already be present
            if "Pictogrammes_DSFR" in image_name:
                pictogram_title = image_name.replace("__", " — ").replace("_", " ")
                self.image_data[i]["filename"] = pictogram_title
                self.image_data[i]["is_pictogram"] = True

            else:
                with requests.get(image_url, timeout=5, stream=True) as image_response:
                    image_response.raise_for_status()
                    with open(self.image_folder / image_name, "wb") as image_file:
                        for chunk in image_response.iter_content(chunk_size=8192):
                            image_file.write(chunk)
                self.image_data[i]["filename"] = image_name
                self.image_data[i]["is_pictogram"] = False

        with open(self.image_data_file, "w") as json_file:
            json.dump(self.image_data, json_file, indent=2)
            json_file.write("\n")

    def import_images(self) -> None:
        """
        Import the images from `image_folder`, and store the ID of each local image
        in the `local_id` key of its entry in `image_data`.
        """
        for i in self.image_ids:
            i = str(i)
            image_data = self.image_data[i]
            filename = image_data["filename"]

            if image_data["is_pictogram"]:
                pictogram = Image.objects.filter(title=filename).first()
                image_data["local_id"] = pictogram.id
            else:
                image = self.get_or_create_image(image_data)
                image_data["local_id"] = image.id

    def get_or_create_image(self, image_data) -> Image:
        """
        Return the local image with the same file hash, or create it from the file in `image_folder`.
        """
        filename = image_data["filename"]
        imported_filename = f"template_image_{filename.lower()}"
        title = image_data["title"]

        with open(self.image_folder / filename, "rb") as image_file:
            file_hash = hash_filelike(image_file)

            image = Image.objects.filter(file_hash=file_hash).first()
            if not image:
                image = Image(
                    file=ImageFile(BytesIO(image_file.read()), name=imported_filename),
                    title=title,
                    uploaded_by_user=self.user,
                    collection=self.collection,
                    created_at=timezone.now(),
                )
                image.save()
                image.get_file_hash()

        return image


def remove_block_ids(json_object):
    """
    Parse a page JSON StreamField representation and strip the block IDs

    Returns a new structure, the original one is not modified.
    """
    if not isinstance(json_object, (dict, list)):
        return json_object
    if isinstance(json_object, list):
        return [remove_block_ids(v) for v in json_object]
    return {k: remove_block_ids(v) for k, v in json_object.items() if k != "id"}


def update_streamfield_image_ids(json_object, image_ids):
    """
    Parse a page JSON StreamField representation and update the image IDs

    `image_ids` maps the source image IDs (as strings) to dicts holding the local ID
    in their `local_id` key, such as `ImportExportImages.image_data`.
    The dicts are updated in place; the updated structure is also returned.
    """
    if isinstance(json_object, dict):
        for k, v in json_object.items():
            v_str = str(v)
            if k in ["image", "bg_image"] and v_str in image_ids:
                json_object[k] = image_ids[v_str]["local_id"]
            else:
                update_streamfield_image_ids(v, image_ids)
    elif isinstance(json_object, list):
        return [update_streamfield_image_ids(v, image_ids) for v in json_object]
    return json_object
