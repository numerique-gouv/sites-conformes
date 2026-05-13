from django.utils.translation import gettext_lazy as _
from dsfr.constants import IMAGE_RATIOS
from wagtail import blocks
from wagtail.blocks import StructValue
from wagtail.images.blocks import ImageBlock, ImageChooserBlock

from sites_conformes.content_manager.blocks.badges_tags import BadgesListBlock, TagListBlock
from sites_conformes.content_manager.constants import (
    HEADING_CHOICES,
    HORIZONTAL_CARD_IMAGE_RATIOS,
    LIMITED_RICHTEXTFIELD_FEATURES,
    LIMITED_RICHTEXTFIELD_FEATURES_WITHOUT_LINKS,
)

from .buttons_links import ButtonsHorizontalListBlock, IconPickerBlock, LinksVerticalListBlock, LinkWithoutLabelBlock


class CardstructValue(StructValue):
    def enlarge_link(self):
        """
        Determine if we need (and can) enlarge the link on the card.
        This requires:
        - That a link is present
        - That no other link is used on the card (such as a tag with a link, or a call-to-action)
        """
        link = self.get("link")
        url = self.get("url")
        document = self.get("document")
        top_detail_badges_tags = self.get("top_detail_badges_tags")
        call_to_action = self.get("call_to_action", "")

        if not ((link and link.url()) or url or document):
            return False

        enlarge = True
        if len(call_to_action):
            enlarge = False
        elif len(top_detail_badges_tags) and top_detail_badges_tags.raw_data[0]["type"] == "tags":
            tags_list = top_detail_badges_tags.raw_data[0]["value"]
            for tag in tags_list:
                if (
                    tag["value"]["link"]["page"] is not None
                    or tag["value"]["link"]["document"] is not None
                    or tag["value"]["link"]["external_url"] != ""
                ):
                    enlarge = False

        return enlarge

    def image_classes(self):
        """
        Determine the image classes for a vertical card. Not used in horizontal card.
        """
        ratio_class = self.get("image_ratio")

        if ratio_class:
            image_classes = f"fr-responsive-img {ratio_class}"
        else:
            image_classes = "fr-responsive-img"

        return image_classes


class CardBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Title"))
    heading_tag = blocks.ChoiceBlock(
        label=_("Heading level"),
        choices=HEADING_CHOICES,
        default="h3",
        help_text=_("Adapt to the page layout. Defaults to heading 3."),
    )
    description = blocks.RichTextBlock(label=_("Content"), features=LIMITED_RICHTEXTFIELD_FEATURES, required=False)
    image = ImageBlock(label=_("Image"), required=False)
    image_ratio = blocks.ChoiceBlock(
        label=_("Image ratio"),
        choices=IMAGE_RATIOS,
        required=False,
        default="h3",
    )
    image_badge = BadgesListBlock(
        label=_("Image area badge"), required=False, help_text=_("Only used if the card has an image."), max_num=1
    )
    link = LinkWithoutLabelBlock(
        label=_("Link"),
        required=False,
        collapsed=False,
        help_text=_(
            "Link for the whole card. If a call-to-action is present, the link will display on the title only."
        ),
    )
    top_detail_text = blocks.CharBlock(label=_("Top detail: text"), required=False)
    top_detail_icon = IconPickerBlock(label=_("Top detail: icon"), required=False)
    top_detail_badges_tags = blocks.StreamBlock(
        [
            ("badges", BadgesListBlock()),
            ("tags", TagListBlock()),
        ],
        label=_("Top detail: badges or tags"),
        max_num=1,
        required=False,
    )
    bottom_detail_text = blocks.CharBlock(
        label=_("Bottom detail: text"),
        help_text=_("Incompatible with the bottom call-to-action."),
        required=False,
    )
    bottom_detail_icon = IconPickerBlock(label=_("Bottom detail: icon"), required=False)
    call_to_action = blocks.StreamBlock(
        [
            (
                "links",
                LinksVerticalListBlock(label=_("Links")),
            ),
            (
                "buttons",
                ButtonsHorizontalListBlock(
                    help_text=_("""Please use only one primary button.
                        If you use icons, use them on all buttons and align them on the same side."""),
                    label=_("Buttons"),
                ),
            ),
        ],
        label=_("Bottom call-to-action: links or buttons"),
        help_text=_("Incompatible with the bottom detail text. Allow you to add link or button."),
        max_num=1,
        required=False,
    )
    grey_background = blocks.BooleanBlock(label=_("Card with grey background"), required=False)
    no_background = blocks.BooleanBlock(label=_("Card without background"), required=False)
    no_border = blocks.BooleanBlock(label=_("Card without border"), required=False)
    shadow = blocks.BooleanBlock(label=_("Card with a shadow"), required=False)

    class Meta:
        icon = "tablet-alt"
        template = "sites_conformes_content_manager/blocks/card.html"
        value_class = CardstructValue


class HorizontalCardBlock(CardBlock):
    image_ratio = blocks.ChoiceBlock(
        label=_("Image ratio"),
        choices=HORIZONTAL_CARD_IMAGE_RATIOS,
        required=False,
        default="h3",
    )
    bottom_detail_text = blocks.CharBlock(
        label=_("Bottom detail: text"),
        help_text=_(
            "Incompatible with the bottom call-to-action. "
            "If the card links to a downloadable document, the values are pre-filled."
        ),
        required=False,
    )

    class Meta:
        icon = "tablet-alt"
        template = "sites_conformes_content_manager/blocks/card_horizontal.html"
        value_class = CardstructValue


class VerticalCardBlock(CardBlock):
    class Meta:
        icon = "tablet-alt"
        template = "sites_conformes_content_manager/blocks/card_vertical.html"
        value_class = CardstructValue


class TileBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Title"))
    heading_tag = blocks.ChoiceBlock(
        label=_("Heading level"),
        choices=HEADING_CHOICES,
        default="h3",
        help_text=_("Adapt to the page layout. Defaults to heading 3."),
    )
    description = blocks.RichTextBlock(
        label=_("Content"), features=LIMITED_RICHTEXTFIELD_FEATURES_WITHOUT_LINKS, required=False
    )
    image = ImageChooserBlock(label=_("Image"), help_text=_("Prefer SVG files."), required=False)
    link = LinkWithoutLabelBlock(
        label=_("Link"),
        required=False,
    )
    top_detail_badges_tags = blocks.StreamBlock(
        [
            ("badges", BadgesListBlock()),
            ("tags", TagListBlock()),
        ],
        label=_("Top detail: badges or tags"),
        max_num=1,
        required=False,
    )
    detail_text = blocks.CharBlock(
        label=_("Detail text"),
        required=False,
        help_text=_("If the tile links to a downloadable document, the values are pre-filled."),
    )
    is_small = blocks.BooleanBlock(label=_("Small tile"), required=False)
    grey_background = blocks.BooleanBlock(label=_("Tile with grey background"), required=False)
    no_background = blocks.BooleanBlock(label=_("Tile without background"), required=False)
    no_border = blocks.BooleanBlock(label=_("Tile without border"), required=False)
    shadow = blocks.BooleanBlock(label=_("Tile with a shadow"), required=False)
    is_horizontal = blocks.BooleanBlock(label=_("Horizontal tile"), required=False)

    class Meta:
        icon = "tablet-alt"
        template = "sites_conformes_content_manager/blocks/tile.html"
        value_class = CardstructValue
