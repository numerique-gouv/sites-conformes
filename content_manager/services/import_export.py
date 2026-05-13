import copy
import json
import os
import sys
from io import BytesIO
from pathlib import PosixPath
from urllib.request import urlretrieve

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.images import ImageFile
from django.utils import timezone
from wagtail.images.models import Image
from wagtail.models import Page
from wagtail.utils.file import hash_filelike

from sites_conformes.content_manager.constants import HEADER_FIELDS
from sites_conformes.content_manager.models import ContentPage
from sites_conformes.content_manager.services.accessors import get_or_create_collection, get_or_create_content_page

PAGE_TEMPLATES_ROOT = settings.BASE_DIR / "content_manager/page_templates"
TEMPLATES_DATA_FILE = PAGE_TEMPLATES_ROOT / "pages_data.json"
IMAGES_FOLDER = PAGE_TEMPLATES_ROOT / "img"

User = get_user_model()


class ExportPage:
    """
    Generic class for export of a ContentPage from a wagtail instance
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
        return self.content

    @property
    def source_page_api_url(self):
        return f"{self.source_site}api/v2/pages/{self.source_page_id}/"

    def get_content_from_source_page(self):
        response = requests.get(self.source_page_api_url)
        return response.json()

    def get_source_images(self) -> None:
        """
        Get a list of images present in the source content.
        """

        # Header image
        header_image = self.source_content.get("header_image", None)
        if header_image:
            header_image["local_image"] = None
            self.image_ids.append(header_image["id"])
            self.content["header_image"]["meta"].pop("download_url")

        # Remove fields with credentials

        # Images from the body
        self.locate_image_ids(self.source_body)
        self.image_ids = list(set(self.image_ids))

    def locate_image_ids(self, json_object):  # NOSONAR
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
        keys = ["parent", "seo_title", "search_description"]
        for key in keys:
            self.content["meta"].pop(key, None)


class ImportPages:
    """
    Generic class for import of a list of ContentPages from a previously made export
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
        # The templates index is created right under the Root page, like a site
        parent_page = Page.objects.first()
        body = [("subpageslist", None)]
        return get_or_create_content_page(
            slug="page_templates_index", title="Modèles de pages à copier", body=body, parent_page=parent_page
        )

    def import_pages(self):
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
        if os.path.isfile(self.image_data_file):
            with open(self.image_data_file, "r") as json_file:
                image_data = json.load(json_file)
        else:
            image_data = {}

        return image_data

    def source_image_api_url(self, image_id: int) -> str:
        return f"{self.source_site}api/v2/images/{image_id}/"

    def get_content_from_source_image(self, image_id: int) -> dict:
        response = requests.get(self.source_image_api_url(image_id))
        return response.json()

    def download_images(self) -> None:
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
                urlretrieve(image_url, self.image_folder / image_name)
                self.image_data[i]["filename"] = image_name
                self.image_data[i]["is_pictogram"] = False

        with open(self.image_data_file, "w") as json_file:
            json.dump(self.image_data, json_file, indent=2)
            json_file.write("\n")

    def import_images(self) -> None:
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
    """
    if not isinstance(json_object, (dict, list)):
        return json_object
    if isinstance(json_object, list):
        return [remove_block_ids(v) for v in json_object]
    return {k: remove_block_ids(v) for k, v in json_object.items() if k != "id"}


def update_streamfield_image_ids(json_object, image_ids):
    """
    Parse a page JSON StreamField representation and update the image IDs
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
