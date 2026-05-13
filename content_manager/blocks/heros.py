from django import forms
from django.forms.utils import ErrorList
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from dsfr.constants import COLOR_CHOICES, IMAGE_RATIOS
from wagtail import blocks
from wagtail.admin.telepath import register
from wagtail.blocks import StructValue
from wagtail.blocks.struct_block import StructBlockAdapter, StructBlockValidationError

from sites_conformes.content_manager.constants import (
    ALIGN_HORIZONTAL_CHOICES_EXTENDED,
    ALIGN_VERTICAL_CHOICES,
    MEDIA_WIDTH_CHOICES,
    TEMPLATE_EXAMPLE_BUTTON_LIST,
)

from .basics import TextContentAllAlignments, TextContentLeftRight, TextContentVerticalAlignments
from .buttons_links import ButtonBlock, ButtonsHorizontalListBlock
from .layout import BackgroundColorChoiceBlock, LayoutBlock
from .medias import ImageBlock, ImageBlockWithDefault


class HeroImageStructValue(StructValue):
    def extra_classes(self):
        """
        Define the extra classes for the image
        """
        image_ratio = self.get("image_ratio")
        image_positioning = self.get("image_positioning")
        extra_class = ""
        if image_ratio:
            extra_class += f"fr-responsive-img {image_ratio} "
        else:
            extra_class += "fr-responsive-img"

        if image_positioning:
            extra_class += f"cmsfr-image-focus-{image_positioning}"
        return extra_class


class HeroImageBlock(blocks.StructBlock):
    image = ImageBlockWithDefault(
        label=_("Image"), default_image_title="Banner Sites Faciles Dimitri Iakymuk Unsplash", required=False
    )
    image_positioning = blocks.ChoiceBlock(
        choices=ALIGN_VERTICAL_CHOICES + ALIGN_HORIZONTAL_CHOICES_EXTENDED,
        label=_("Image positioning"),
        required=False,
        default="bottom",
        help_text=_("Choose the part of the image to highlight"),
    )


class HeroImageBlockWithRatioWidth(HeroImageBlock):
    image_width = blocks.ChoiceBlock(
        label=_("Image width"),
        choices=MEDIA_WIDTH_CHOICES,
        required=False,
        default="fr-content-media--lg",
        help_text=_("Select image width"),
    )
    image_ratio = blocks.ChoiceBlock(
        label=_("Image ratio"),
        choices=IMAGE_RATIOS,
        required=False,
        default="fr-ratio-32x9",
        help_text=_(
            "Select the right ratio for your image. "
            "The size will be adjusted on mobile phones, so make sure you don't include any text in the image."
        ),
    )

    class Meta:
        value_class = HeroImageStructValue


class HeroImageBlockWithMask(HeroImageBlock):
    # Overriding image_positioning to offer fewer options than in HeroImageBlock
    image_positioning = blocks.ChoiceBlock(
        choices=[
            ("top", _("Top")),
            ("bottom", _("Bottom")),
            ("", _("Center")),
        ],
        label=_("Image positioning"),
        required=False,
        default="",
        help_text=_("Choose the part of the image to highlight"),
    )

    image_mask = blocks.ChoiceBlock(
        label=_("Image mask"),
        choices=[
            ("darken", _("Darken")),
            ("lighten", _("Lighten")),
        ],
        required=False,
        default="",
        help_text=_("Add a mask to lighten or darken the image"),
    )

    class Meta:
        value_class = HeroImageStructValue


class HeroImageAndTextBlock(blocks.StructBlock):
    text_content = TextContentLeftRight(label=_("Text content"))
    buttons = blocks.ListBlock(
        ButtonBlock(label=_("Button")),
        default=TEMPLATE_EXAMPLE_BUTTON_LIST,
        label=_("Buttons"),
        help_text=_("""Please use only one primary button.
            If you use icons, use them on all buttons and align them on the same side."""),
    )
    image = ImageBlockWithDefault(label=_("Hero image"), default_image_title="Illustration Sites Faciles Homme Nuages")
    layout = LayoutBlock(label=_("Layout"))

    class Meta:
        icon = "minus"
        template = "sites_conformes_content_manager/heros/hero_image_text.html"


class HeroWideImageAndTextBlock(blocks.StructBlock):
    text_content = TextContentVerticalAlignments(label=_("Text content"))
    layout = LayoutBlock(label=_("Layout"))
    buttons = blocks.ListBlock(
        ButtonBlock(label=_("Button")),
        default=TEMPLATE_EXAMPLE_BUTTON_LIST,
        label=_("Buttons"),
        help_text=_("""Please use only one primary button.
            If you use icons, use them on all buttons and align them on the same side."""),
    )
    image = HeroImageBlockWithRatioWidth(
        label=_("Hero image"),
    )

    class Meta:
        icon = "minus"
        template = "sites_conformes_content_manager/heros/hero_wide_image_text.html"


class HeroBackgroundImageBlock(blocks.StructBlock):
    text_content = TextContentAllAlignments(label=_("Text content"))
    buttons = blocks.ListBlock(
        ButtonBlock(label=_("Button")),
        default=TEMPLATE_EXAMPLE_BUTTON_LIST,
        label=_("Buttons"),
        help_text=_("""Please use only one primary button.
            If you use icons, use them on all buttons and align them on the same side."""),
    )
    background_color_or_image = blocks.ChoiceBlock(
        choices=[("color", _("Color")), ("image", _("Image"))],
        label=_("Background Color or Image"),
        required=False,
        default="image",
        help_text=_("Choose if you prefer a background image or a background color."),
    )
    image = HeroImageBlockWithMask(
        label=_("Hero image"),
    )
    background_color = BackgroundColorChoiceBlock(
        label=_("Background color"),
        required=False,
        help_text=_(
            "Uses the French Design System colors.<br>"
            "If you want to design a classic website, choose the colour ‘white’ or ‘French blue’."
        ),
    )

    class Meta:
        icon = "minus"
        template = "sites_conformes_content_manager/heros/hero_background_image_text.html"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.background_types = ["color", "image"]

    def clean(self, value):
        if value is None:
            value = {}
        errors = {}
        selected_background_type = value.get("background_color_or_image")

        if not selected_background_type:
            for background_type in self.background_types:
                if background_type == "color" and value.get("background_color"):
                    selected_background_type = "color"
                    value["background_color_or_image"] = "color"
                    break
                elif background_type == "image" and value.get("image"):
                    selected_background_type = "image"
                    value["background_color_or_image"] = "image"
                    break
                else:
                    selected_background_type = "image"
                    value["background_color_or_image"] = "image"

        if selected_background_type == "color":
            if not value.get("background_color"):
                errors["background_color"] = ErrorList([_("Please select a color for the background.")])
        elif selected_background_type == "image":
            if not value.get("image"):
                errors["image"] = ErrorList([_("Please select an image for the background.")])

        if errors:
            raise StructBlockValidationError(block_errors=errors)

        if selected_background_type == "color":
            value["image"] = {}
        elif selected_background_type == "image":
            value["background_color"] = None

        return super().clean(value)


class HeroBackgroundBlockAdapter(StructBlockAdapter):
    js_constructor = "blocks.HeroBackgroundImageBlock"

    @cached_property
    def media(self):

        structblock_media = super().media
        return forms.Media(
            js=structblock_media._js + ["js/hero-background-block.js"],
        )


register(HeroBackgroundBlockAdapter(), HeroBackgroundImageBlock)


class OldHero(blocks.StructBlock):
    header_with_title = blocks.BooleanBlock(
        label=_("Show title in header image?"),
        required=False,
    )
    header_image = ImageBlock(label=_("Header image"), required=False)
    header_color_class = blocks.ChoiceBlock(
        label=_("Background color"),
        choices=COLOR_CHOICES,
        required=False,
        help_text=_("Uses the French Design System colors. Apply only if there is no header image."),
    )
    header_large = blocks.BooleanBlock(
        label=_("Centered title"),
        required=False,
        help_text=_("If checked, the title will be centered on the header."),
    )
    header_darken = blocks.BooleanBlock(label=_("Darken background image"), required=False)
    header_cta_text = blocks.RichTextBlock(label=_("Call to action text"), null=True, blank=True, required=False)
    header_cta_buttons = ButtonsHorizontalListBlock(required=False, label=_("Buttons"))

    class Meta:
        icon = "minus"
        help_text = _(
            "This block allows you to create a fully configurable header.\n"
            "It corresponds to the historical header block used since the beginning of the project."
        )
        template = "sites_conformes_content_manager/heros/old_hero.html"
