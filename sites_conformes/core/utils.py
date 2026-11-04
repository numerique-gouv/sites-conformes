from io import BytesIO

from django.core.files.images import ImageFile
from dsfr.constants import IMAGE_RATIOS
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


def get_closest_image_ratio(image) -> str:
    """
    Returns the DSFR ratio class (such as "fr-ratio-4x3") closest to the proportions of an image,
    or of any object with a width and a height, such as a rendition.

    The DSFR displays the images of content medias in 16:9 when no ratio is chosen,
    which distorts them: the closest ratio crops them as little as possible.
    """
    proportions = image.width / image.height

    def distance(choice):
        width, height = choice[1].split("x")
        return abs(int(width) / int(height) - proportions)

    return min(IMAGE_RATIOS, key=distance)[0]


def get_default_site() -> Site:
    """
    Returns the default site, or the first one if none is set.
    """
    site = Site.objects.filter(is_default_site=True).first()

    if not site:
        site = Site.objects.filter().first()

    return site  # type: ignore
