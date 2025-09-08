import os

from django.core.management.base import BaseCommand
from wagtail.images.models import Image

from content_manager.services.accessors import get_or_create_collection
from content_manager.utils import import_image


class Command(BaseCommand):
    help = """
    Import all illustration images for block template.

    Should only be launched if the statics have been collected at least once.
    """

    def handle(self, *args, **kwargs):
        image_root = "staticfiles/illustration/"
        files = os.listdir(image_root)
        files.sort()

        collection = get_or_create_collection("Images d'illustration")

        for filename in files:
            file_path = os.path.join(image_root, filename)

            base_file_title = filename.split(".")[0].replace("-", " ").title()

            image_exists = Image.objects.filter(title=base_file_title).first()
            if image_exists:
                file_hash = image_exists.get_file_hash()
                self.stdout.write(f"A image named {base_file_title} already exists, skipping (file_hash: {file_hash})")
                continue

            image = import_image(full_path=file_path, title=base_file_title)
            image.collection = collection
            image.save()
            image.get_file_hash()
            self.stdout.write(f"Image {base_file_title} imported")
