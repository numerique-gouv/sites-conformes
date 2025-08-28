from django import forms
from django.forms.utils import ErrorList
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _, pgettext_lazy
from dsfr.constants import COLOR_CHOICES, COLOR_CHOICES_ILLUSTRATION, COLOR_CHOICES_SYSTEM, IMAGE_RATIOS, VIDEO_RATIOS
from wagtail import blocks
from wagtail.blocks import BooleanBlock, StructValue
from wagtail.blocks.struct_block import StructBlockAdapter, StructBlockValidationError
from wagtail.contrib.typed_table_block.blocks import TypedTableBlock
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.images.blocks import ImageBlock, ImageChooserBlock
from wagtail.snippets.blocks import SnippetChooserBlock
from wagtail.telepath import register
from wagtailmarkdown.blocks import MarkdownBlock

from content_manager.constants import (
    ALIGN_HORIZONTAL_CHOICES,
    ALIGN_HORIZONTAL_CHOICES_EXTENDED,
    ALIGN_VERTICAL_CHOICES,
    BUTTON_ICON_SIDE,
    BUTTON_TYPE_CHOICES,
    BUTTONS_ALIGN_CHOICES,
    GRID_3_4_6_CHOICES,
    GRID_HORIZONTAL_ALIGN_CHOICES,
    GRID_VERTICAL_ALIGN_CHOICES,
    HEADING_CHOICES,
    HEADING_CHOICES_2_5,
    HORIZONTAL_CARD_IMAGE_RATIOS,
    LEVEL_CHOICES,
    LIMITED_RICHTEXTFIELD_FEATURES,
    LIMITED_RICHTEXTFIELD_FEATURES_WITHOUT_LINKS,
    LINK_ICON_CHOICES,
    LINK_SIZE_CHOICES,
    MEDIA_WIDTH_CHOICES,
    TEXT_SIZE_CHOICES,
)
from content_manager.widgets import DsfrIconPickerWidget

# Wagtail Block Documentation : https://docs.wagtail.org/en/stable/reference/streamfield/blocks.html


# Table-related blocks
class PictogramBlock(ImageBlock):
    # A subclass of ImageBlock with the height fixed to 80px.
    class Meta:
        icon = "image"
        template = "content_manager/widgets/pictogram.html"


class AdvancedTypedTableBlock(TypedTableBlock):
    row_heading = blocks.CharBlock(required=False, label=_("Row heading"))
    text = blocks.RichTextBlock(features=LIMITED_RICHTEXTFIELD_FEATURES, required=False, label=_("Text"))
    pictogram = PictogramBlock(required=False, label=_("Pictogram"))

    class Meta:
        icon = "table"
        template = "content_manager/blocks/typed_table_block.html"
        help_text = _('The "row heading" column type only works on the first column of the table.')


## Meta blocks
class BackgroundColorChoiceBlock(blocks.ChoiceBlock):
    choices = COLOR_CHOICES

    class Meta:
        icon = "view"


class IconPickerBlock(blocks.FieldBlock):
    def __init__(self, required=True, help_text=None, validators=(), **kwargs):
        self.field_options = {
            "required": required,
            "help_text": help_text,
            "max_length": 70,
            "min_length": 0,
            "validators": [],
        }
        super().__init__(**kwargs)

    @cached_property
    def field(self):
        field_kwargs = {"widget": DsfrIconPickerWidget()}
        field_kwargs.update(self.field_options)
        return forms.CharField(**field_kwargs)

    class Meta:
        icon = "radio-full"


class LinkStructValue(blocks.StructValue):
    def url(self):
        link = self.get("external_url", "")

        page = self.get("page")
        document = self.get("document")

        if page:
            link = page.url
        elif document:
            link = document.url

        return link


class LinkWithoutLabelBlock(blocks.StructBlock):
    LINK_TYPE_CHOICES = [
        ("page", _("Page")),
        ("external_url", _("External URL")),
        ("document", _("Document")),
    ]

    link_type = blocks.ChoiceBlock(
        choices=LINK_TYPE_CHOICES,
        required=True,
        label=_("Link type"),
        help_text=_("Select the type of link."),
    )
    page = blocks.PageChooserBlock(
        label=_("Page"),
        required=False,
        help_text=_("Link to a page of this site. Use either this, the document, or the external URL parameter."),
    )
    document = DocumentChooserBlock(
        label=_("Document"),
        help_text=_("Use either this, the external URL or the page parameter."),
        required=False,
    )
    external_url = blocks.URLBlock(
        label=_("External URL"),
        required=False,
        help_text=_("Use either this, the document or the page parameter."),
    )

    class Meta:
        value_class = LinkStructValue
        icon = "link"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.link_types = [choice[0] for choice in self.LINK_TYPE_CHOICES]

    def clean(self, value):
        errors = {}
        selected_link_type = value.get("link_type")
        if not selected_link_type:
            for link_type in self.link_types:
                if value.get(link_type):
                    selected_link_type = link_type
                    value["link_type"] = link_type
                    break
        match selected_link_type:
            case "page":
                internal_page = value.get("page")
                if not internal_page:
                    errors["page"] = ErrorList([_("Please select a page to link to")])
            case "external_url":
                external_url = value.get("external_url")
                if not external_url:
                    errors["external_url"] = ErrorList([_("Please enter a URL")])
            case "document":
                document = value.get("document")
                if not document:
                    errors["document"] = ErrorList([_("Please select a document to link to")])
        if errors:
            raise StructBlockValidationError(block_errors=errors)

        for link_type in self.link_types:
            if link_type != selected_link_type:
                value[link_type] = None
        return super().clean(value)


class LinkBlock(LinkWithoutLabelBlock):
    text = blocks.CharBlock(label=_("Link label"), required=False)

    class Meta:
        value_class = LinkStructValue
        icon = "link"


class LinksVerticalListBlock(blocks.StreamBlock):
    link = LinkBlock(label=_("Link"))

    class Meta:
        icon = "list-ul"
        template = "content_manager/blocks/links_vertical_list.html"


class ButtonBlock(LinkWithoutLabelBlock):
    text = blocks.CharBlock(label=_("Button label"), required=False)
    button_type = blocks.ChoiceBlock(label=_("Button type"), choices=BUTTON_TYPE_CHOICES, required=False)
    icon_class = IconPickerBlock(label=_("Icon"), required=False)
    icon_side = blocks.ChoiceBlock(
        label=_("Icon side"),
        choices=BUTTON_ICON_SIDE,
        required=False,
        default="",
    )

    class Meta:
        value_class = LinkStructValue
        icon = "link"


class ButtonsHorizontalListBlock(blocks.StreamBlock):
    button = ButtonBlock(label=_("Button"))

    class Meta:
        icon = "list-ul"
        template = "content_manager/blocks/buttons_horizontal_list.html"


class ButtonsVerticalListBlock(blocks.StreamBlock):
    button = ButtonBlock(label=_("Button"))

    class Meta:
        icon = "list-ul"
        template = "content_manager/blocks/buttons_vertical_list.html"


class ButtonsListBlock(blocks.StructBlock):
    buttons = ButtonsHorizontalListBlock(
        label=_("Buttons"),
        help_text=_(
            """Please use only one primary button.
            If you use icons, use them on all buttons and align them on the same side."""
        ),
    )
    position = blocks.ChoiceBlock(label=_("Position"), choices=BUTTONS_ALIGN_CHOICES, default="", required=False)

    class Meta:
        icon = "list-ul"
        template = "content_manager/blocks/buttons_list.html"


class SingleLinkBlock(LinkBlock):
    icon = blocks.ChoiceBlock(
        label=_("Icon"),
        help_text=_("Only used for internal links."),
        choices=LINK_ICON_CHOICES,
        required=False,
        default="",
    )
    size = blocks.ChoiceBlock(
        label=_("Size"),
        choices=LINK_SIZE_CHOICES,
        required=False,
        default="",
    )

    class Meta:
        value_class = LinkStructValue
        icon = "link"
        template = "content_manager/blocks/link.html"


## Badges and Tags
badge_level_choices = (
    ("", [("new", _("New")), ("grey", _("Grey"))]),
    (_("System colors"), COLOR_CHOICES_SYSTEM),
    (_("Illustration colors"), COLOR_CHOICES_ILLUSTRATION),
)


class BadgeBlock(blocks.StructBlock):
    text = blocks.CharBlock(label=_("Badge label"), required=False)
    color = blocks.ChoiceBlock(label=_("Badge color"), choices=badge_level_choices, required=False)
    hide_icon = blocks.BooleanBlock(label=_("Hide badge icon"), required=False)

    class Meta:
        template = "content_manager/blocks/badge.html"


class BadgesListBlock(blocks.StreamBlock):
    badge = BadgeBlock(label=_("Badge"))

    class Meta:
        icon = "list-ul"
        template = "content_manager/blocks/badges_list.html"


class TagBlock(blocks.StructBlock):
    label = blocks.CharBlock(label=_("Title"))
    is_small = blocks.BooleanBlock(label=_("Small tag"), required=False)
    color = blocks.ChoiceBlock(
        label=_("Tag color"),
        choices=COLOR_CHOICES_ILLUSTRATION,
        required=False,
        help_text=_("Only for clickable tags"),
    )
    icon_class = IconPickerBlock(label=_("Icon"), required=False)
    link = LinkWithoutLabelBlock(required=False)

    class Meta:
        template = "content_manager/blocks/tag.html"


class TagListBlock(blocks.StreamBlock):
    tag = TagBlock(label=pgettext_lazy("DSFR Tag", "Tag"))

    class Meta:
        icon = "list-ul"
        template = "content_manager/blocks/tags_list.html"


## Cards and tiles
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
    image = ImageChooserBlock(label=_("Image"), required=False)
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
    )
    url = blocks.URLBlock(
        label=_("Link (obsolete)"),
        required=False,
        group="target",
        help_text=_(
            "This field is obsolete and will be removed in the near future. Please replace with the Link field above."
        ),
    )
    document = DocumentChooserBlock(
        label=_("or Document (obsolete)"),
        required=False,
        group="target",
        help_text=_(
            "This field is obsolete and will be removed in the near future. Please replace with the Link field above."
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
            ("links", LinksVerticalListBlock()),
            (
                "buttons",
                ButtonsHorizontalListBlock(
                    help_text=_(
                        """Please use only one primary button.
                        If you use icons, use them on all buttons and align them on the same side."""
                    ),
                    label=_("Buttons"),
                ),
            ),
        ],
        label=_("Bottom call-to-action: links or buttons"),
        help_text=_("Incompatible with the bottom detail text."),
        max_num=1,
        required=False,
    )
    grey_background = blocks.BooleanBlock(label=_("Card with grey background"), required=False)
    no_background = blocks.BooleanBlock(label=_("Card without background"), required=False)
    no_border = blocks.BooleanBlock(label=_("Card without border"), required=False)
    shadow = blocks.BooleanBlock(label=_("Card with a shadow"), required=False)

    class Meta:
        icon = "tablet-alt"
        template = "content_manager/blocks/card.html"
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
        template = "content_manager/blocks/card_horizontal.html"
        value_class = CardstructValue


class VerticalCardBlock(CardBlock):
    class Meta:
        icon = "tablet-alt"
        template = "content_manager/blocks/card_vertical.html"
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
        template = "content_manager/blocks/tile.html"
        value_class = CardstructValue


## Basic blocks
class AccordionBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Title"))
    content = blocks.RichTextBlock(label=_("Content"))


class AccordionsBlock(blocks.StreamBlock):
    title = blocks.CharBlock(label=_("Title"))
    accordion = AccordionBlock(label=_("Accordion"), min_num=1, max_num=15)

    class Meta:
        template = "content_manager/blocks/accordions.html"


class AlertBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Message title"), required=False)
    description = blocks.TextBlock(label=_("Message text"), required=False)
    level = blocks.ChoiceBlock(label=_("Message type"), choices=LEVEL_CHOICES)
    heading_tag = blocks.ChoiceBlock(
        label=_("Heading level"),
        choices=HEADING_CHOICES,
        default="h3",
        help_text=_("Adapt to the page layout. Defaults to heading 3."),
    )

    class Meta:
        icon = "info-circle"
        template = "content_manager/blocks/alert.html"


class CalloutBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Title"), required=False)
    heading_tag = blocks.ChoiceBlock(
        label=_("Heading level"),
        choices=HEADING_CHOICES,
        default="h3",
        help_text=_("Adapt to the page layout. Defaults to heading 3."),
    )
    icon_class = IconPickerBlock(label=_("Icon"), required=False)

    text = blocks.RichTextBlock(label=_("Content"), features=LIMITED_RICHTEXTFIELD_FEATURES, required=False)
    button = ButtonBlock(label=_("Button"), required=False)
    color = blocks.ChoiceBlock(
        label=_("Color"),
        choices=COLOR_CHOICES_ILLUSTRATION,
        required=False,
    )

    class Meta:
        icon = "info-circle"
        template = "content_manager/blocks/callout.html"


class HighlightBlock(blocks.StructBlock):
    text = blocks.RichTextBlock(label=_("Content"), features=LIMITED_RICHTEXTFIELD_FEATURES)
    color = blocks.ChoiceBlock(
        label=_("Color"),
        choices=COLOR_CHOICES_ILLUSTRATION,
        required=False,
    )
    size = blocks.ChoiceBlock(
        label=_("Size"),
        choices=TEXT_SIZE_CHOICES,
        required=False,
    )

    class Meta:
        icon = "info-circle"
        template = "content_manager/blocks/highlight.html"


class IframeBlock(blocks.StructBlock):
    title = blocks.CharBlock(
        label=_("Title"),
        help_text=_("Accessibility: The title should describe, in a clear and concise manner, the embedded content."),
    )
    url = blocks.URLBlock(
        label=_("URL of the iframe"),
        help_text=_("Example for Tally: https://tally.so/embed/w2jMRa"),
    )
    height = blocks.IntegerBlock(label=_("Height (in pixels)"))
    parameters = blocks.CharBlock(
        label=_("Parameters"),
        help_text=_("""For example: "allow='geolocation'"."""),
        required=False,
    )

    class Meta:
        icon = "globe"
        template = "content_manager/blocks/iframe.html"


class ImageAndTextBlock(blocks.StructBlock):
    image = ImageBlock(label=_("Image"))
    image_side = blocks.ChoiceBlock(
        label=_("Image position"),
        choices=[
            ("left", _("Left (displayed above text in mobile view)")),
            ("left_below", _("Left (displayed below text in mobile view)")),
            ("right", _("Right (displayed below text in mobile view)")),
            ("right_above", _("Right (displayed above text in mobile view)")),
        ],
        default="right",
    )
    image_ratio = blocks.ChoiceBlock(
        label=_("Image width"),
        choices=[
            ("3", "3/12"),
            ("4", "4/12"),
            ("5", "5/12"),
            ("6", "6/12"),
        ],
        default="3",
    )
    text = blocks.RichTextBlock(label=_("Rich text"))
    link = SingleLinkBlock(
        label=_("Link"),
        required=False,
        help_text=_("The link is shown at the bottom of the text block, with an arrow"),
    )
    link_label = blocks.CharBlock(
        label=_("Link label (obsolete)"),
        required=False,
        help_text=_(
            "This field is obsolete and will be removed in the near future. Please replace with the Link field above."
        ),
        group="obsolete",
    )
    page = blocks.PageChooserBlock(
        label=_("Internal link (obsolete)"),
        required=False,
        help_text=_(
            "This field is obsolete and will be removed in the near future. Please replace with the Link field above."
        ),
        group="obsolete",
    )
    link_url = blocks.URLBlock(
        label=_("Link URL (obsolete)"),
        required=False,
        help_text=_(
            "This field is obsolete and will be removed in the near future. Please replace with the Link field above."
        ),
        group="obsolete",
    )

    class Meta:
        icon = "image"
        template = "content_manager/blocks/image_and_text.html"


class CenteredImageStructValue(StructValue):
    def extra_classes(self):
        """
        Define the extra classes for the image
        """
        image_ratio = self.get("image_ratio")

        if image_ratio:
            return f"fr-responsive-img {image_ratio}"
        else:
            return "fr-responsive-img"


class CenteredImageBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Title"), required=False)
    heading_tag = blocks.ChoiceBlock(
        label=_("Heading level"),
        choices=HEADING_CHOICES,
        required=False,
        default="h3",
        help_text=_("Adapt to the page layout. Defaults to heading 3."),
    )
    image = ImageChooserBlock(label=_("Image"))
    alt = blocks.CharBlock(
        label=_("Alternative text (textual description of the image)"),
        required=False,
    )
    width = blocks.ChoiceBlock(
        label=_("Witdh"),
        choices=MEDIA_WIDTH_CHOICES,
        required=False,
        default="",
    )
    image_ratio = blocks.ChoiceBlock(
        label=_("Image ratio"),
        choices=IMAGE_RATIOS,
        required=False,
        default="h3",
    )
    caption = blocks.CharBlock(label=_("Caption"), required=False)
    url = blocks.URLBlock(label=_("Link"), required=False)

    class Meta:
        icon = "image"
        template = "content_manager/blocks/image.html"
        value_class = CenteredImageStructValue


class QuoteBlock(blocks.StructBlock):
    image = ImageChooserBlock(label=_("Image"), required=False)
    quote = blocks.CharBlock(label=_("Quote"))
    author_name = blocks.CharBlock(label=_("Author name"), required=False)
    author_title = blocks.CharBlock(label=_("Author title"), required=False)
    color = blocks.ChoiceBlock(
        label=_("Color"),
        choices=COLOR_CHOICES_ILLUSTRATION,
        required=False,
    )

    class Meta:
        icon = "openquote"
        template = "content_manager/blocks/quote.html"


class SeparatorBlock(blocks.StructBlock):
    top_margin = blocks.IntegerBlock(label=_("Top margin"), min_value=0, max_value=15, default=3)
    bottom_margin = blocks.IntegerBlock(label=_("Bottom margin"), min_value=0, max_value=15, default=3)


class StepBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Title"))
    detail = blocks.TextBlock(label=_("Detail"), required=False)


class StepsListBlock(blocks.StreamBlock):
    step = StepBlock(label=_("Step"))


class StepperBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Title"))
    total = blocks.IntegerBlock(label=_("Number of steps"), min_value=1, max_value=8)
    current = blocks.IntegerBlock(label=_("Current step"), min_value=1, max_value=8)
    steps = StepsListBlock(label=_("Steps"))

    class Meta:
        template = "content_manager/blocks/stepper.html"


class TextAndCTA(blocks.StructBlock):
    text = blocks.RichTextBlock(label=_("Rich text"), required=False)
    cta_buttons = blocks.StreamBlock(
        [
            (
                "buttons",
                ButtonsHorizontalListBlock(
                    help_text=_(
                        """Please use only one primary button.
                        If you use icons, use them on all buttons and align them on the same side."""
                    ),
                    label=_("Buttons"),
                ),
            ),
        ],
        label=_("Call-to-action buttons"),
        max_num=1,
        required=False,
    )
    cta_label = blocks.CharBlock(
        label=_("Call to action label  (obsolete)"),
        help_text=_(
            "This field is obsolete and will be removed in the near future. Please replace with the CTA buttons above."
        ),
        required=False,
    )
    cta_url = blocks.CharBlock(
        label=_("Link (obsolete)"),
        help_text=_(
            "This field is obsolete and will be removed in the near future. Please replace with the CTA buttons above."
        ),
        required=False,
    )

    class Meta:
        icon = "link"
        template = "content_manager/blocks/text_and_cta.html"


class TranscriptionBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Title"), default="Transcription", required=False)
    content = blocks.RichTextBlock(label=_("Transcription content"), required=False)

    class Meta:
        icon = "media"
        template = "content_manager/blocks/transcription.html"


class VideoBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Video title"), required=False)
    caption = blocks.CharBlock(label=_("Caption"), required=False)
    url = blocks.URLBlock(
        label=_("Video URL"),
        help_text=_(
            "Use embed format, with a version that doesn't require a consent banner if available."
            " (e.g. : https://www.youtube-nocookie.com/embed/gLzXOViPX-0)"
            " For Youtube, use Embed video and check Enable privacy-enhanced mode."
        ),
    )

    width = blocks.ChoiceBlock(
        label=_("Witdh"),
        choices=MEDIA_WIDTH_CHOICES,
        required=False,
        default="",
    )
    video_ratio = blocks.ChoiceBlock(
        label=_("Video ratio"),
        choices=VIDEO_RATIOS,
        required=False,
        default="h3",
    )
    transcription = TranscriptionBlock(label=_("Transcription"), required=False)

    class Meta:
        icon = "media"
        template = "content_manager/blocks/video.html"


class VerticalContactCardStructValue(blocks.StructValue):
    def display(self):
        contact = self.get("contact", None)

        name = self.get("name", "")
        if contact and not name:
            name = contact.name

        role = self.get("role", "")
        if contact and not role:
            role = contact.role

        organization = self.get("organization", "")
        if contact and not organization:
            organization = contact.organization.name

        image = self.get("image", "")
        if contact and not image:
            image = contact.image

        return {"name": name, "role": role, "organization": organization, "image": image}

    def enlarge_link(self):
        """
        Determine if we need (and can) enlarge the link on the card.
        This requires:
        - That a link is present
        - That no other link is used on the card (such as a tag with a link, or a call-to-action)
        """
        link = self.get("link")
        tags = self.get("tags")
        call_to_action = self.get("call_to_action", "")

        if not (link and link.url()):
            return False

        enlarge = True
        if len(call_to_action):
            enlarge = False
        elif len(tags):
            tags_list = tags.raw_data
            for tag in tags_list:
                if (
                    tag["value"]["link"]["page"] is not None
                    or tag["value"]["link"]["document"] is not None
                    or tag["value"]["link"]["external_url"] != ""
                ):
                    enlarge = False

        return enlarge


class VerticalContactCardBlock(blocks.StructBlock):
    contact = SnippetChooserBlock(
        "blog.Person",
        label=_("Person"),
        help_text=_("Optional, all values can be manually specified or overriden below"),
        required=False,
    )
    link = LinkWithoutLabelBlock(
        label=_("Link"),
        required=False,
    )
    heading_tag = blocks.ChoiceBlock(
        label=_("Heading level"),
        choices=HEADING_CHOICES,
        required=False,
        default="h3",
        help_text=_("Adapt to the page layout. Defaults to heading 3."),
    )
    name = blocks.CharBlock(label=_("Name"), max_length=255, required=False)
    role = blocks.CharBlock(label=_("Role"), max_length=255, required=False)
    organization = blocks.CharBlock(label=_("Organization"), max_length=255, required=False)
    contact_info = blocks.CharBlock(label=_("Contact info"), max_length=500, required=False)
    image = ImageChooserBlock(label="Image", required=False)
    tags = TagListBlock(label=_("Tags"), required=False)

    class Meta:
        icon = "user"
        value_class = VerticalContactCardStructValue
        template = ("content_manager/blocks/contact_card_vertical.html",)


## Other apps-related blocks
class RecentEntriesStructValue(blocks.StructValue):
    """
    Get and filter the recent entries for either a blog index or an events page index
    """

    def posts(self):
        index_page = self.get("index_page")
        is_blog = False

        if not index_page:
            is_blog = True
            index_page = self.get("blog")

        posts = index_page.posts

        category_filter = self.get("category_filter")
        if category_filter:
            if is_blog:
                posts = posts.filter(blog_categories=category_filter)
            else:
                posts = posts.filter(event_categories=category_filter)

        tag_filter = self.get("tag_filter")
        if tag_filter:
            posts = posts.filter(tags=tag_filter)

        author_filter = self.get("author_filter")
        if author_filter:
            posts = posts.filter(authors=author_filter)

        source_filter = self.get("source_filter")
        if source_filter:
            posts = posts.filter(authors__organization=source_filter)

        entries_count = self.get("entries_count")
        return posts[:entries_count]

    def current_filters(self) -> dict:
        filters = {}

        category_filter = self.get("category_filter")
        if category_filter:
            filters["category"] = category_filter.slug

        tag_filter = self.get("tag_filter")
        if tag_filter:
            filters["tag"] = tag_filter.slug

        author_filter = self.get("author_filter")
        if author_filter:
            filters["author"] = author_filter.id

        source_filter = self.get("source_filter")
        if source_filter:
            filters["source"] = source_filter.slug

        return filters

    def sub_heading_tag(self):
        """
        Used for the filters section titles
        """
        heading_tag = self.get("heading_tag")
        if heading_tag == "h2":
            return "h3"
        elif heading_tag == "h3":
            return "h4"
        elif heading_tag == "h4":
            return "h5"
        else:
            return "h6"


class BlogRecentEntriesBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Title"), required=False)
    heading_tag = blocks.ChoiceBlock(
        label=_("Heading level"),
        choices=HEADING_CHOICES_2_5,
        required=False,
        default="h2",
        help_text=_("Adapt to the page layout. Defaults to heading 2."),
    )
    blog = blocks.PageChooserBlock(label=_("Blog"), page_type="blog.BlogIndexPage")
    entries_count = blocks.IntegerBlock(
        label=_("Number of entries"), required=False, min_value=1, max_value=8, default=3
    )
    category_filter = SnippetChooserBlock("blog.Category", label=_("Filter by category"), required=False)
    tag_filter = SnippetChooserBlock("content_manager.Tag", label=_("Filter by tag"), required=False)
    author_filter = SnippetChooserBlock("blog.Person", label=_("Filter by author"), required=False)
    source_filter = SnippetChooserBlock(
        "blog.Organization",
        label=_("Filter by source"),
        help_text=_("The source is the organization of the post author"),
        required=False,
    )
    show_filters = BooleanBlock(label=_("Show filters"), default=False, required=False)

    class Meta:
        icon = "placeholder"
        template = ("content_manager/blocks/blog_recent_entries.html",)
        value_class = RecentEntriesStructValue


class EventsRecentEntriesBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Title"), required=False)
    heading_tag = blocks.ChoiceBlock(
        label=_("Heading level"),
        choices=HEADING_CHOICES_2_5,
        required=False,
        default="h2",
        help_text=_("Adapt to the page layout. Defaults to heading 2."),
    )
    index_page = blocks.PageChooserBlock(label=_("Event calendar"), page_type="events.EventsIndexPage")
    entries_count = blocks.IntegerBlock(
        label=_("Number of entries"), required=False, min_value=1, max_value=8, default=3
    )
    category_filter = SnippetChooserBlock("blog.Category", label=_("Filter by category"), required=False)
    tag_filter = SnippetChooserBlock("content_manager.Tag", label=_("Filter by tag"), required=False)
    author_filter = SnippetChooserBlock("blog.Person", label=_("Filter by author"), required=False)
    source_filter = SnippetChooserBlock(
        "blog.Organization",
        label=_("Filter by source"),
        help_text=_("The source is the organization of the post author"),
        required=False,
    )
    show_filters = BooleanBlock(label=_("Show filters"), default=False, required=False)

    class Meta:
        icon = "placeholder"
        template = ("content_manager/blocks/events_recent_entries.html",)
        value_class = RecentEntriesStructValue


## Page structure blocks
class CommonStreamBlock(blocks.StreamBlock):
    text = blocks.RichTextBlock(label=_("Rich text"))
    image = CenteredImageBlock(label=_("Centered image"))
    imageandtext = ImageAndTextBlock(label=_("Image and text"))
    table = AdvancedTypedTableBlock(label=_("Table"))
    alert = AlertBlock(label=_("Alert message"))
    text_cta = TextAndCTA(label=_("Text and call to action"))
    video = VideoBlock(label=_("Video"))
    transcription = TranscriptionBlock(label=_("Transcription"))
    badges_list = BadgesListBlock(label=_("Badge list"))
    tags_list = TagListBlock(label=_("Tag list"))
    buttons_list = ButtonsListBlock(label=_("Button list"))
    accordions = AccordionsBlock(label=_("Accordions"), group=_("DSFR components"))
    callout = CalloutBlock(label=_("Callout"), group=_("DSFR components"))
    highlight = HighlightBlock(label=_("Highlight"), group=_("DSFR components"))
    quote = QuoteBlock(label=_("Quote"), group=_("DSFR components"))
    stepper = StepperBlock(label=_("Stepper"), group=_("DSFR components"))
    link = SingleLinkBlock(label=_("Single link"))
    iframe = IframeBlock(label=_("Iframe"), group=_("DSFR components"))
    tile = TileBlock(label=_("Tile"), group=_("DSFR components"))
    blog_recent_entries = BlogRecentEntriesBlock(label=_("Blog recent entries"), group=_("Website structure"))
    events_recent_entries = EventsRecentEntriesBlock(
        label=_("Event calendar recent entries"), group=_("Website structure")
    )
    stepper = StepperBlock(label=_("Stepper"), group=_("DSFR components"))
    markdown = MarkdownBlock(label=_("Markdown"), group=_("Expert syntax"))
    iframe = IframeBlock(label=_("Iframe"), group=_("Expert syntax"))
    html = blocks.RawHTMLBlock(
        readonly=True,
        help_text=_("Warning: Use HTML block with caution. Malicious code can compromise the security of the site."),
        group=_("Expert syntax"),
    )
    separator = SeparatorBlock(label=_("Separator"), group=_("Page structure"))

    class Meta:
        icon = "dots-horizontal"


class ColumnBlock(CommonStreamBlock):
    card = VerticalCardBlock(label=_("Vertical card"), group=_("DSFR components"))
    contact_card = VerticalContactCardBlock(label=_("Contact card"), group=_("Extra components"))


class GridPositionStructValue(blocks.StructValue):
    def grid_position(self):
        position = []

        horizontal_align = self.get("horizontal_align", None)
        if horizontal_align:
            position.append(f"fr-grid-row--{horizontal_align}")

        vertical_align = self.get("vertical_align", None)
        if vertical_align:
            position.append(f"fr-grid-row--{vertical_align}")

        return " ".join(position)


class ItemGridBlock(blocks.StructBlock):
    column_width = blocks.ChoiceBlock(
        label=_("Column width"),
        choices=GRID_3_4_6_CHOICES,
        default="4",
    )
    horizontal_align = blocks.ChoiceBlock(
        label=_("Horizontal align"), choices=GRID_HORIZONTAL_ALIGN_CHOICES, default="left", required=False
    )
    vertical_align = blocks.ChoiceBlock(label=_("Vertical align"), choices=GRID_VERTICAL_ALIGN_CHOICES, required=False)
    items = ColumnBlock(label=_("Items"))

    class Meta:
        icon = "grip"
        template = "content_manager/blocks/item_grid.html"
        value_class = GridPositionStructValue


class TabBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Title"))
    content = ColumnBlock(label=_("Content"))


class TabsBlock(blocks.StreamBlock):
    tabs = TabBlock(label=_("Tab"), min_num=1, max_num=15)

    class Meta:
        template = "content_manager/blocks/tabs.html"


class AdjustableColumnBlock(blocks.StructBlock):
    width = blocks.ChoiceBlock(
        label=_("Column width"),
        choices=[
            ("3", "3/12"),
            ("4", "4/12"),
            ("5", "5/12"),
            ("6", "6/12"),
            ("7", "7/12"),
            ("8", "8/12"),
            ("9", "9/12"),
        ],
        help_text=_("The total width of all columns should be 12."),
        required=False,
    )
    content = ColumnBlock(label=_("Column content"))

    class Meta:
        icon = "order-down"


class BlockMarginStructValue(blocks.StructValue):
    def vertical_margin(self):
        margin = []

        top_margin = self.get("top_margin", None)
        if top_margin:
            margin.append(f"fr-mt-{top_margin}w")

        bottom_margin = self.get("bottom_margin", None)
        if bottom_margin:
            margin.append(f"fr-mb-{bottom_margin}w")

        return " ".join(margin)


class MultiColumnsStructValue(BlockMarginStructValue, GridPositionStructValue):
    pass


class MultiColumnsBlock(CommonStreamBlock):
    card = VerticalCardBlock(label=_("Vertical card"), group=_("DSFR components"))
    column = AdjustableColumnBlock(label=_("Adjustable column"), group=_("Page structure"))

    class Meta:
        icon = "dots-horizontal"


class MultiColumnsWithTitleBlock(blocks.StructBlock):
    bg_image = ImageChooserBlock(label=_("Background image"), required=False)
    bg_color_class = BackgroundColorChoiceBlock(
        label=_("Background color"),
        required=False,
        help_text=_("Uses the French Design System colors"),
    )
    bg_color = blocks.RegexBlock(
        label=_("Background color, hexadecimal format (obsolete)"),
        regex=r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$",
        help_text=_(
            "This field is obsolete and will be removed in the near future. Replace it with the background color."  # noqa
        ),
        error_messages={"invalid": _("Incorrect color format, must be #fff or #f5f5f5")},
        required=False,
    )
    title = blocks.CharBlock(label=_("Title"), required=False)
    heading_tag = blocks.ChoiceBlock(
        label=_("Heading level"),
        choices=HEADING_CHOICES,
        required=False,
        default="h2",
        help_text=_("Adapt to the page layout. Defaults to heading 2."),
    )
    top_margin = blocks.IntegerBlock(
        label=_("Top margin"),
        min_value=0,
        max_value=15,
        default=5,
        required=False,
    )
    bottom_margin = blocks.IntegerBlock(
        label=_("Bottom margin"),
        min_value=0,
        max_value=15,
        default=5,
        required=False,
    )
    vertical_align = blocks.ChoiceBlock(label=_("Vertical align"), choices=GRID_VERTICAL_ALIGN_CHOICES, required=False)

    columns = MultiColumnsBlock(label=_("Columns"))

    class Meta:
        icon = "dots-horizontal"
        template = "content_manager/blocks/multicolumns.html"
        value_class = MultiColumnsStructValue


class FullWidthBlock(CommonStreamBlock):
    image_and_text = ImageAndTextBlock(label=_("Image and text"))
    card = HorizontalCardBlock(label=_("Horizontal card"), group=_("DSFR components"))
    tabs = TabsBlock(label=_("Tabs"), group=_("DSFR components"))
    item_grid = ItemGridBlock(label=_("Item grid"), group=_("Page structure"))

    class Meta:
        icon = "minus"


class FullWidthBackgroundBlock(blocks.StructBlock):
    bg_image = ImageChooserBlock(label=_("Background image"), required=False)
    bg_color_class = BackgroundColorChoiceBlock(
        label=_("Background color"),
        required=False,
        help_text=_("Uses the French Design System colors"),
    )
    top_margin = blocks.IntegerBlock(
        label=_("Top margin"),
        min_value=0,
        max_value=15,
        default=5,
        required=False,
    )
    bottom_margin = blocks.IntegerBlock(
        label=_("Bottom margin"),
        min_value=0,
        max_value=15,
        default=5,
        required=False,
    )

    content = FullWidthBlock(label=_("Content"))

    class Meta:
        icon = "minus"
        template = "content_manager/blocks/full_width_background.html"
        value_class = BlockMarginStructValue


class PageTreeBlock(blocks.StructBlock):
    page = blocks.PageChooserBlock(label=_("Parent page"))

    class Meta:
        icon = "minus"
        template = "content_manager/blocks/pagetree.html"


class SideMenuBlock(blocks.StreamBlock):
    html = blocks.RawHTMLBlock(
        label="HTML",
        help_text=_("Warning: Use HTML block with caution. Malicious code can compromise the security of the site."),
    )
    pagetree = PageTreeBlock(label=_("Page tree"))

    class Meta:
        icon = "minus"


class FullWidthBackgroundWithSidemenuBlock(blocks.StructBlock):
    bg_image = ImageChooserBlock(label=_("Background image"), required=False)
    bg_color_class = BackgroundColorChoiceBlock(
        label=_("Background color"),
        required=False,
        help_text=_("Uses the French Design System colors"),
    )
    top_margin = blocks.IntegerBlock(
        label=_("Top margin"),
        min_value=0,
        max_value=15,
        default=5,
        required=False,
    )
    bottom_margin = blocks.IntegerBlock(
        label=_("Bottom margin"),
        min_value=0,
        max_value=15,
        default=5,
        required=False,
    )

    main_content = FullWidthBlock(label=_("Main content"))
    sidemenu_title = blocks.CharBlock(label=_("Side menu title"), required=False)
    sidemenu_content = SideMenuBlock(label=_("Side menu content"))

    class Meta:
        icon = "minus"
        template = "content_manager/blocks/full_width_background_with_sidemenu.html"
        value_class = BlockMarginStructValue


STREAMFIELD_COMMON_BLOCKS = [
    ("paragraph", blocks.RichTextBlock(label=_("Rich text"))),
    ("image", CenteredImageBlock(label=_("Centered image"))),
    ("imageandtext", ImageAndTextBlock(label=_("Image and text"))),
    ("table", AdvancedTypedTableBlock(label=_("Table"))),
    ("alert", AlertBlock(label=_("Alert message"))),
    ("text_cta", TextAndCTA(label=_("Text and call to action"))),
    ("video", VideoBlock(label=_("Video"))),
    ("transcription", TranscriptionBlock(label=_("Transcription"))),
    ("badges_list", BadgesListBlock(label=_("Badge list"))),
    ("tags_list", TagListBlock(label=_("Tag list"))),
    ("buttons_list", ButtonsListBlock(label=_("Button list"))),
    ("link", SingleLinkBlock(label=_("Single link"))),
    ("accordions", AccordionsBlock(label=_("Accordions"), group=_("DSFR components"))),
    ("callout", CalloutBlock(label=_("Callout"), group=_("DSFR components"))),
    ("highlight", HighlightBlock(label=_("Highlight"), group=_("DSFR components"))),
    ("quote", QuoteBlock(label=_("Quote"), group=_("DSFR components"))),
    ("stepper", StepperBlock(label=_("Stepper"), group=_("DSFR components"))),
    ("card", HorizontalCardBlock(label=_("Horizontal card"), group=_("DSFR components"))),
    ("tile", TileBlock(label=_("Tile"), group=_("DSFR components"))),
    ("tabs", TabsBlock(label=_("Tabs"), group=_("DSFR components"))),
    ("markdown", MarkdownBlock(label=_("Markdown"), group=_("Expert syntax"))),
    ("iframe", IframeBlock(label=_("Iframe"), group=_("Expert syntax"))),
    (
        "html",
        blocks.RawHTMLBlock(
            readonly=True,
            help_text=_(
                "Warning: Use HTML block with caution. Malicious code can compromise the security of the site."
            ),
            group=_("Expert syntax"),
        ),
    ),
    ("separator", SeparatorBlock(label=_("Separator"), group=_("Page structure"))),
    ("multicolumns", MultiColumnsWithTitleBlock(label=_("Multiple columns"), group=_("Page structure"))),
    ("item_grid", ItemGridBlock(label=_("Item grid"), group=_("Page structure"))),
    ("fullwidthbackground", FullWidthBackgroundBlock(label=_("Full width background"), group=_("Page structure"))),
    (
        "fullwidthbackgroundwithsidemenu",
        FullWidthBackgroundWithSidemenuBlock(
            label=_("Full width background with side menu"), group=_("Page structure")
        ),
    ),
    (
        "subpageslist",
        blocks.StaticBlock(
            label=_("Subpages list"),
            admin_text=_("A simple, alphabetical list of the subpages of the current page."),
            template="content_manager/blocks/subpages_list.html",
            group=_("Website structure"),
        ),
    ),
    (
        "blog_recent_entries",
        BlogRecentEntriesBlock(label=_("Blog recent entries"), group=_("Website structure")),
    ),
    (
        "events_recent_entries",
        EventsRecentEntriesBlock(label=_("Event calendar recent entries"), group=_("Website structure")),
    ),
]


class LinkBlockAdapter(StructBlockAdapter):
    js_constructor = "blocks.links.LinkBlock"

    def js_args(self, block):
        # keys added to args[2] found in this.meta in StructBlockDefinition
        args = super().js_args(block)
        # link types configured in LinkBlock class instance
        args[2]["link_types"] = block.link_types
        return args

    @cached_property
    def media(self):
        from django import forms

        structblock_media = super().media
        return forms.Media(
            js=structblock_media._js + ["js/link-block.js"],
        )


register(LinkBlockAdapter(), LinkWithoutLabelBlock)


## Hero blocks


class MarginBlock(blocks.StructBlock):
    top_margin = blocks.IntegerBlock(
        label=_("Top margin"),
        min_value=0,
        max_value=15,
        default=5,
        required=False,
    )
    bottom_margin = blocks.IntegerBlock(
        label=_("Bottom margin"),
        min_value=0,
        max_value=15,
        default=5,
        required=False,
    )

    class Meta:
        value_class = BlockMarginStructValue


class LayoutBlock(MarginBlock):
    background_color = BackgroundColorChoiceBlock(
        label=_("Background color"),
        required=False,
        help_text=_(
            "Uses the French Design System colors.<br>"
            "If you want to design a classic website, choose the colour ‘white’ or ‘French blue’."
        ),
    )


class TextContentBlock(blocks.StructBlock):
    hero_title = blocks.CharBlock(
        label=_("Title header"),
        help_text=_("The title that will appear in the header of your page"),
        default=_("The title of your header"),
    )
    hero_subtitle = blocks.RichTextBlock(
        features=LIMITED_RICHTEXTFIELD_FEATURES,
        required=False,
        label=_("Text"),
        help_text=_("To give a brief description of what you do"),
        default=_("Add a short description of your organisation here to help visitors easily understand what you do."),
    )


class TextContentLeftRight(TextContentBlock):
    position = blocks.ChoiceBlock(choices=ALIGN_HORIZONTAL_CHOICES, position_default="")


class TextContentAllAlignments(TextContentBlock):
    position = blocks.ChoiceBlock(choices=ALIGN_HORIZONTAL_CHOICES_EXTENDED, default="center")


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
    image = ImageChooserBlock(label=_("Image"))
    image_positioning = blocks.ChoiceBlock(
        choices=ALIGN_VERTICAL_CHOICES + ALIGN_HORIZONTAL_CHOICES,
        label=_("Image positioning"),
        required=False,
        default="center",
        help_text=_("Choose the part of the image to highlight"),
    )

    class Meta:
        value_class = HeroImageStructValue


class HeroImageBlockWithRatioWidth(HeroImageBlock):
    image_width = blocks.ChoiceBlock(
        label=_("Image width"),
        choices=MEDIA_WIDTH_CHOICES,
        required=False,
        default="",
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
    image_positioning = blocks.ChoiceBlock(
        choices=[
            ("top", _("Top")),
            ("bottom", _("Bottom")),
            ("center", _("Center")),
        ],
        label=_("Image positioning"),
        required=False,
        default="center",
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
    def __init__(self, position_default="left", **kwargs):
        local_blocks = (
            (
                "text_content",
                blocks.StructBlock(
                    [
                        (
                            "hero_title",
                            blocks.CharBlock(
                                label=_("Title header"),
                                help_text=_("The title that will appear " "in the header of your page"),
                                default=_("The title of your header"),
                            ),
                        ),
                        (
                            "hero_subtitle",
                            blocks.RichTextBlock(
                                features=LIMITED_RICHTEXTFIELD_FEATURES,
                                required=False,
                                label=_("Text"),
                                help_text=_("To give a brief description of what you do"),
                                default=_(
                                    "Add a short description of "
                                    "your organisation here to help visitors easily understand what you do."
                                ),
                            ),
                        ),
                        (
                            "position",
                            blocks.ChoiceBlock(
                                choices=ALIGN_HORIZONTAL_CHOICES,
                                default=position_default,
                                label=_("Position"),
                            ),
                        ),
                    ],
                    label=_("Text content"),
                ),
            ),
            (
                "buttons",
                blocks.ListBlock(
                    ButtonBlock(),
                    default=[
                        {
                            "link_type": "external_url",
                            "text": "Nous contacter",
                            "external_url": "https://sites.beta.gouv.fr/contactez-nous/",
                            "button_type": "fr-btn",
                            "icon_side": "--",
                        },
                        {
                            "link_type": "external_url",
                            "text": "Voir la vidéo",
                            "external_url": "http://google.com",
                            "button_type": "fr-btn fr-btn--secondary",
                            "icon_side": "--t",
                        },
                    ],
                ),
            ),
            ("image", ImageChooserBlock(label=_("Hero image"))),
            ("layout", LayoutBlock(label=_("Layout"))),
        )
        super().__init__(local_blocks, **kwargs)

    class Meta:
        icon = "minus"
        template = "content_manager/heros/hero_image_text.html"


class HeroWideImageAndTextBlock(blocks.StructBlock):
    def __init__(self, position_default="left", **kwargs):
        local_blocks = (
            (
                "text_content",
                blocks.StructBlock(
                    [
                        (
                            "hero_title",
                            blocks.CharBlock(
                                label=_("Title header"),
                                help_text=_("The title that will appear " "in the header of your page"),
                                default=_("The title of your header"),
                            ),
                        ),
                        (
                            "hero_subtitle",
                            blocks.RichTextBlock(
                                features=LIMITED_RICHTEXTFIELD_FEATURES,
                                required=False,
                                label=_("Text"),
                                help_text=_("To give a brief description of what you do"),
                                default=_(
                                    "Add a short description of your "
                                    "organisation here to help visitors easily understand what you do."
                                ),
                            ),
                        ),
                        (
                            "position",
                            blocks.ChoiceBlock(
                                choices=ALIGN_VERTICAL_CHOICES,
                                default=position_default,
                                label=_("Text content Position"),
                            ),
                        ),
                    ],
                    label=_("Text content"),
                ),
            ),
            (
                "layout",
                blocks.StructBlock(
                    [
                        (
                            "top_margin",
                            blocks.IntegerBlock(
                                label=_("Spacing above text content"),
                                min_value=0,
                                max_value=15,
                                default=5,
                                required=False,
                            ),
                        ),
                        (
                            "bottom_margin",
                            blocks.IntegerBlock(
                                label=_("Spacing below text content"),
                                min_value=0,
                                max_value=15,
                                default=5,
                                required=False,
                            ),
                        ),
                        (
                            "background_color",
                            BackgroundColorChoiceBlock(
                                label=_("Background color"),
                                required=False,
                                help_text=_(
                                    "Uses the French Design System colors.<br>"
                                    "If you want to design a classic website, "
                                    "choose the colour ‘white’ or ‘French blue’."
                                ),
                            ),
                        ),
                    ],
                    label=_(""),
                    value_class=BlockMarginStructValue,
                ),
            ),
            (
                "buttons",
                blocks.ListBlock(
                    ButtonBlock(),
                    default=[
                        {
                            "link_type": "external_url",
                            "text": "Nous contacter",
                            "external_url": "https://sites.beta.gouv.fr/contactez-nous/",
                            "button_type": "fr-btn",
                            "icon_side": "--",
                        },
                        {
                            "link_type": "external_url",
                            "text": "Voir la vidéo",
                            "external_url": "http://google.com",
                            "button_type": "fr-btn fr-btn--secondary",
                            "icon_side": "--",
                        },
                    ],
                ),
            ),
            (
                "image",
                HeroImageBlockWithRatioWidth(
                    label=_("Hero image"),
                    default={
                        "image_ratio": "fr-ratio-32x9",
                        "image_width": "",
                    },
                ),
            ),
        )
        super().__init__(local_blocks, **kwargs)

    class Meta:
        icon = "minus"
        template = "content_manager/heros/hero_wide_image_text.html"


class HeroBackgroundImageBlock(blocks.StructBlock):
    text_content = TextContentAllAlignments()
    buttons = blocks.ListBlock(
        ButtonBlock(),
        default=[
            {
                "link_type": "external_url",
                "text": "Nous contacter",
                "external_url": "https://sites.beta.gouv.fr/contactez-nous/",
                "button_type": "fr-btn",
                "icon_side": "--",
            },
            {
                "link_type": "external_url",
                "text": "Voir la vidéo",
                "external_url": "http://google.com",
                "button_type": "fr-btn fr-btn--secondary",
                "icon_side": "--",
            },
        ],
    )
    image = HeroImageBlockWithMask(label=_("Hero image"))

    class Meta:
        icon = "minus"
        template = "content_manager/heros/hero_background_image_text.html"


class OldHero(blocks.StructBlock):
    header_with_title = blocks.BooleanBlock(label=_("Show title in header image?"), required=False)
    header_image = ImageChooserBlock(label=_("Header image"), required=False)
    header_color_class = blocks.ChoiceBlock(
        label=_("Background color"),
        choices=COLOR_CHOICES,
        required=False,
        help_text=_("Uses the French Design System colors"),
    )

    header_large = blocks.BooleanBlock(label=_("Full width"), required=False)
    header_darken = blocks.BooleanBlock(label=_("Darken background image"), required=False)
    header_cta_text = blocks.RichTextBlock(
        label=_("Call to action text"),
        null=True,
        blank=True,
    )
    header_cta_buttons = ButtonsHorizontalListBlock(required=False)

    class Meta:
        icon = "minus"
        admin_text = (
            "Ce bloc récupère les données des anciennes en-têtes mais n'est pas configurable. "
            "Veuillez choisir un autre modèle d'en-tête."
        )
        template = "content_manager/heros/old_hero.html"


HERO_STREAMFIELD_BLOCKS = [
    ("header_1", HeroImageAndTextBlock(position_default="left", label=_("En-tête 1"))),
    ("header_2", HeroImageAndTextBlock(position_default="right", label=_("En-tête 2"))),
    ("header_3", HeroWideImageAndTextBlock(position_default="top", label=_("En-tête 3"))),
    ("header_4", HeroWideImageAndTextBlock(position_default="bottom", label=_("En-tête 4"))),
    ("header_5", HeroBackgroundImageBlock(label=_("En-tête 5"))),
    ("old_hero", OldHero(label=_("Ancienne en-tête"))),
]
