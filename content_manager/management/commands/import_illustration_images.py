import os

from django.core.management.base import BaseCommand
from wagtail.images.models import Image

from sites_conformes.content_manager.services.accessors import get_or_create_collection
from sites_conformes.content_manager.utils import import_image, overwrite_image


class Command(BaseCommand):
    help = """
    Import all illustration images for block template.

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

        image_root = "staticfiles/illustration/"
        files = os.listdir(image_root)
        files.sort()

        collection = get_or_create_collection("Illustrations par défaut")

        exists_counter = 0
        imported_counter = 0

        for filename in files:
            file_path = os.path.join(image_root, filename)

            base_file_title = filename.split(".")[0].replace("-", " ").title()

            image_exists = Image.objects.filter(title=base_file_title).first()
            if image_exists and not force_update:
                file_hash = image_exists.get_file_hash()
                exists_counter += 1
                if verbosity > 1:
                    self.stdout.write(
                        f"A image named {base_file_title} already exists, skipping (file_hash: {file_hash})"
                    )
            elif image_exists and force_update:
                if verbosity > 1:
                    self.stdout.write(f"Overwriting image {image_exists} with file {filename}.")

                image = overwrite_image(
                    image=image_exists,
                    full_file_path=file_path,
                    title=base_file_title,
                )
                image.get_file_hash()
                exists_counter += 1

            else:
                image = import_image(full_file_path=file_path, title=base_file_title)
                image.collection = collection
                image.save()
                image.get_file_hash()
                imported_counter += 1

                if verbosity > 1:
                    self.stdout.write(f"Image {base_file_title} imported")

        if force_update:
            exists_message = "images forcefully updated"
        else:
            exists_message = "already existing images skipped"
        self.stdout.write(
            f"Illustration images: {imported_counter} images imported, {exists_counter} {exists_message}."
        )
