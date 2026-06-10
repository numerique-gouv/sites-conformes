import logging
import re
from html import unescape
from io import BytesIO
from pathlib import Path

from bs4 import BeautifulSoup
from django.core.files.images import ImageFile
from wagtail.images import get_image_model
from wagtail.models import Site

logger = logging.getLogger(__name__)

Image = get_image_model()


def _build_image_name(full_file_path: str, content: bytes) -> str:
    """
    Build the stored filename for an imported image, ensuring it keeps a usable
    extension. Wagtail's rendition generation (and the ``{% picture %}`` tag)
    chokes on files stored without an extension, so we sniff one when missing
    and log loudly when detection fails rather than silently creating a broken,
    extension-less image.
    """
    path = Path(full_file_path)
    ext = guess_extension(full_file_path, content)
    if not ext:
        logger.warning(
            "Could not determine an extension for image %r; storing it without " "one may break rendition generation.",
            full_file_path,
        )
    return f"{path.stem}{ext}"


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
    """
    content = Path(full_file_path).read_bytes()
    name = _build_image_name(full_file_path, content)
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
    name = _build_image_name(full_file_path, content)
    image.file = ImageFile(BytesIO(content), name=name)
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


def get_streamblock_raw_text(block) -> str:
    """
    Get the raw text of a streamblock.
    """

    # Remove entirely some block types
    removable_blocks = ["image", "alert", "video", "stepper", "separator", "html", "iframe"]

    raw_text = ""
    if block.block.name == "imageandtext":
        raw_text += block.value["text"].source
    elif block.block.name == "multicolumns":
        for column in block.value["columns"]:
            raw_text += get_streamblock_raw_text(column)
    elif block.block.name not in removable_blocks:
        raw_text += block.render()

    return raw_text


def get_streamfield_raw_text(streamfield, max_words: int | None = None) -> str:
    """
    Get the raw text of a streamfield. Used to pre-fill the search description field
    """

    raw_html = ""
    raw_text = ""
    for block in streamfield:
        raw_html += get_streamblock_raw_text(block)

    if not raw_html:
        return ""

    soup = BeautifulSoup(raw_html, "html.parser")
    raw_text += soup.get_text(" ")

    raw_text = unescape(raw_text)
    raw_text = re.sub(r" +", " ", raw_text).strip()

    if max_words:
        words = raw_text.split()
        raw_text = " ".join(words[:max_words]) + " […]"

    return raw_text
