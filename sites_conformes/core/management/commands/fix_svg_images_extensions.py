from pathlib import PurePosixPath

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from wagtail.images import get_image_model


def rename_wagtail_image(image, new_filename):
    old_file = image.file
    # Capture the original name and storage as plain values before saving:
    # image.file.save() mutates image.file (and therefore old_file, which is
    # the same FieldFile object) to point at the new name, so reading
    # old_file.name afterwards would yield the new name and delete the file we
    # just created.
    old_name = old_file.name
    old_storage = old_file.storage

    old_file.open()
    try:
        content = old_file.read()
    finally:
        old_file.close()

    image.file.save(new_filename, ContentFile(content), save=False)
    old_storage.delete(old_name)

    # Update only file field prevents erroring on width / height
    # fields that needs to be calculated for non-svg files
    image.save(update_fields=["file"])


class Command(BaseCommand):
    help = """
    Fix all svg images extensions to prevent images with no extensions to make
    wagtail rendition generation to choke when using picture tag

    See https://github.com/wagtail/wagtail/blob/f96b1fb829b107d1f90bcc6fee2fbf8c9d82263f/wagtail/images/models.py#L902
    is_svg is called during this process and won't work with images without extension.

    This script is inspired by https://github.com/wagtail/wagtail/blob/f96b1fb829b107d1f90bcc6fee2fbf8c9d82263f/wagtail/images/tests/tests.py#L388C1-L388C51
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without applying them.",
        )

    def handle(self, *args, **kwargs):
        dry_run = kwargs["dry_run"]
        # Only files without an extension can be SVGs that Wagtail fails to recognise,
        # skipping the others avoids downloading every image on each deploy
        for image in get_image_model().objects.exclude(file__regex=r"\.[^/]+$"):
            try:
                with image.get_willow_image() as willow_image:
                    is_svg = willow_image.format_name == "svg"
            except OSError as e:
                # A missing or unreadable file must not abort the deployment
                self.stderr.write(f"Skipping image {image.pk} ({image.file.name}): {e}")
                continue

            if not is_svg:
                continue

            # upload_to adds the folder back, so only pass the file name
            filename = f"{PurePosixPath(image.file.name).name}.svg"
            self.stdout.write(f"Image {image.pk}: {image.file.name} -> {filename}")
            if not dry_run:
                rename_wagtail_image(image, filename)
