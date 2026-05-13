import re
from html import unescape
from io import BytesIO

from bs4 import BeautifulSoup
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
