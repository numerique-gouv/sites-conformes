"""
Generic helpers for images and sites, with no dependency on the project models.

Helpers that need the project models (get or create pages, menus, collections…)
live in `sites_conformes.core.services.accessors` to avoid circular imports.
"""

import logging
from io import BytesIO
from pathlib import Path

from django.core.files.images import ImageFile
from dsfr.constants import IMAGE_RATIOS
from wagtail.images import get_image_model
from wagtail.models import Site

logger = logging.getLogger(__name__)

Image = get_image_model()


def _build_image_name(full_file_path: str, title: str, content: bytes) -> str:
    """
    Build the stored filename for an imported image from its title (exports detect
    pictograms by "Pictogrammes_DSFR" in it), ensuring it keeps a usable
    extension. Wagtail's rendition generation (and the ``{% picture %}`` tag)
    chokes on files stored without an extension, so we sniff one when missing
    and log loudly when detection fails rather than silently creating a broken,
    extension-less image.
    """
    ext = guess_extension(full_file_path, content)
    if not ext:
        logger.warning(
            "Could not determine an extension for image %r; storing it without " "one may break rendition generation.",
            full_file_path,
        )
    return f"{title}{ext}"


def guess_extension(filename: str, file_content: bytes) -> str:
    """
    Return the file extension (with leading dot) for *filename*.
    If the filename already has an extension, it is returned as-is.
    Otherwise the type is sniffed from magic bytes.
    """
    ext = Path(filename).suffix
    if ext:
        return ext.lower()

    if file_content[:4] == b"\x89PNG":
        return ".png"
    if file_content[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if file_content[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if file_content[:4] == b"RIFF" and file_content[8:12] == b"WEBP":
        return ".webp"
    # AVIF / HEIF share the ISOBMFF "ftyp" box; the brand at bytes 8-12
    # distinguishes AVIF. WAGTAILIMAGES_EXTENSIONS now allows avif uploads.
    if file_content[4:8] == b"ftyp" and file_content[8:12] in (b"avif", b"avis"):
        return ".avif"
    if b"<svg" in file_content[:512].lower():
        return ".svg"

    return ""


def import_image(full_file_path: str, title: str) -> Image:
    """
    Import an image to the Wagtail medias based on its full path and return it.

    A new image is created at each call, even if the same file was already imported:
    use `overwrite_image` to update an existing one.
    """
    content = Path(full_file_path).read_bytes()
    name = _build_image_name(full_file_path, title, content)
    image = Image(
        file=ImageFile(BytesIO(content), name=name),
        title=title,
    )
    image.save()
    return image


def overwrite_image(image, full_file_path: str, title: str) -> Image:
    """
    Overwrites the file for a Wagtail image instance,
    keeping the same database record and ID.
    """
    content = Path(full_file_path).read_bytes()
    name = _build_image_name(full_file_path, title, content)
    image.file = ImageFile(BytesIO(content), name=name)
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
