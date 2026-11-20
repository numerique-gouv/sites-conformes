"""
Pages exercising the image display options of #597, for e2e/image-ratios.spec.ts.

Run with `python manage.py shell -c "exec(open('e2e/image_ratios_fixtures.py').read())"`:
it (re)creates the pages under /e2e-image-ratios/ each time.
"""

from io import BytesIO

import swapper
from django.core.files.images import ImageFile
from dsfr.constants import IMAGE_RATIOS
from PIL import Image as PILImage
from wagtail.images import get_image_model

from sites_conformes.core.constants import IMAGE_FORMAT_CHOICES
from sites_conformes.core.utils import get_default_site

ContentPage = swapper.load_model("sites_conformes_core", "ContentPage")
Image = get_image_model()

PARENT_SLUG = "e2e-image-ratios"


def get_or_create_image(title, size):
    image = Image.objects.filter(title=title).first()
    if image:
        return image
    # 2:1, a ratio no option offers, so a crop always shows
    content = BytesIO()
    PILImage.new("RGB", size, "#6a6af4").save(content, "PNG")
    return Image.objects.create(title=title, file=ImageFile(content, name=f"{title}.png"))


wide = get_or_create_image("e2e-wide", (1800, 900))
small = get_or_create_image("e2e-small", (400, 200))


def image_value(image):
    return {"image": image, "alt_text": "", "decorative": True}


def text_content(title):
    return {"hero_title": title, "position": "left"}


def hero_text_image(image_format, image_size=""):
    return (
        "hero_text_image",
        {
            "text_content": text_content("Image et texte"),
            "buttons": [],
            "image": image_value(wide),
            "image_format": image_format,
            "image_size": image_size,
        },
    )


def hero_background(background_format):
    return (
        "hero_text_background_image",
        {
            "text_content": text_content("Image de fond"),
            "buttons": [],
            "background_color_or_image": "image",
            "image": {"image": image_value(wide), "background_format": background_format},
        },
    )


def centered_image(caption, image=wide, width="", image_ratio="original"):
    # The caption identifies the block in the test
    return ("image", {"image": image_value(image), "width": width, "image_ratio": image_ratio, "caption": caption})


# "fr-responsive-img--16x9" -> "16x9", "" -> "original"
heroes = {
    f"hero-{value.rsplit('--', 1)[-1] or 'original'}": [hero_text_image(value)] for value, _ in IMAGE_FORMAT_CHOICES
}
heroes |= {f"hero-size-{size}": [hero_text_image("", size)] for size in ("sm", "md")}
heroes |= {f"background-{fmt or 'standard'}": [hero_background(fmt)] for fmt in ("", "32x9", "16x9")}

centered = [
    centered_image("original-sm", width="fr-content-media--sm"),
    centered_image("original-md"),
    centered_image("original-lg", width="fr-content-media--lg"),
    centered_image("natural", image=small, width="natural"),
    *(centered_image(ratio, image_ratio=ratio) for ratio, _ in IMAGE_RATIOS),
]

for page in ContentPage.objects.filter(slug=PARENT_SLUG):
    page.delete()

parent = get_default_site().root_page.add_child(instance=ContentPage(title="E2E image ratios", slug=PARENT_SLUG))
for slug, hero in heroes.items():
    parent.add_child(instance=ContentPage(title=slug, slug=slug, hero=hero))
parent.add_child(instance=ContentPage(title="Centered images", slug="centered-images", body=centered))
