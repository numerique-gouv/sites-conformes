import os

from django.core.management.base import BaseCommand
from wagtail.images.models import Image

from sites_conformes.content_manager.services.accessors import get_or_create_collection
from sites_conformes.content_manager.utils import import_image, overwrite_image


class Command(BaseCommand):
    help = """
    Import all the pictograms from the DSFR.

    Should only be launched if the statics have been collected at least once.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force the update of the image even if it already exists",
        )

    def handle(self, *args, **kwargs):
        verbosity = int(kwargs.get("verbosity", 1))
        force_update = kwargs.get("force")

        picto_root = "staticfiles/dsfr/dist/artwork/pictograms/"
        picto_folders = os.listdir(picto_root)
        picto_folders.sort()

        exists_counter = 0
        imported_counter = 0

        collection = get_or_create_collection("Pictogrammes DSFR")

        for folder in picto_folders:
            folder_path = os.path.join(picto_root, folder)
            files = os.listdir(folder_path)
            files = [f for f in files if f.endswith(".svg")]
            files.sort()

            folder_title = folder.capitalize()

            for filename in files:
                file_path = os.path.join(folder_path, filename)

                base_file_title = filename.split(".")[0].replace("-", " ").title()
                full_image_title = f"Pictogrammes DSFR — {folder_title} — {base_file_title}"

                image_exists = Image.objects.filter(title=full_image_title).first()
                if image_exists and not force_update:
                    file_hash = image_exists.get_file_hash()
                    exists_counter += 1
                    if verbosity > 1:
                        self.stdout.write(
                            f"A file named {full_image_title} already exists, skipping (file_hash: {file_hash})"
                        )
                elif image_exists and force_update:
                    if verbosity > 1:
                        self.stdout.write(f"Overwriting image {image_exists} with file {filename}.")

                    image = overwrite_image(
                        image=image_exists,
                        full_file_path=file_path,
                        title=full_image_title,
                    )
                    image.get_file_hash()
                    exists_counter += 1

                else:
                    image = import_image(
                        full_file_path=file_path,
                        title=full_image_title,
                    )

                    image.collection = collection
                    image.save()
                    image.get_file_hash()

                    image.tags.add("DSFR")
                    image.tags.add("Pictogrammes")
                    image.tags.add(folder_title)

                    imported_counter += 1
                    if verbosity > 1:
                        self.stdout.write(f"File {full_image_title} imported")

        if force_update:
            exists_message = "images forcefully updated"
        else:
            exists_message = "already existing images skipped"
        self.stdout.write(f"DSFR pictograms: {imported_counter} images imported, {exists_counter} {exists_message}.")
