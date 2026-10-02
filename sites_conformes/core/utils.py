from io import BytesIO

from django.core.files.images import ImageFile
from wagtail.images import get_image_model
from wagtail.models import Site

Image = get_image_model()


def import_image(full_file_path: str, title: str):
    """
    Import an image to the Wagtail medias based on its full path and return it.
    """
    with open(full_file_path, "rb") as image_file:
        image = Image(
            file=ImageFile(BytesIO(image_file.read()), name=title),
            title=title,
        )
        image.save()
        return image


def overwrite_image(image, full_file_path: str, title: str):
    """
    Overwrites the file for a Wagtail image instance,
    keeping the same database record and ID.
    """
    with open(full_file_path, "rb") as image_file:
        image.file = ImageFile(BytesIO(image_file.read()), name=title)
        image.save()

    return image


def get_default_site() -> Site:
    """
    Returns the default site, or the first one if none is set.
    """
    site = Site.objects.filter(is_default_site=True).first()

    if not site:
        site = Site.objects.filter().first()

    return site  # type: ignore
