from django.utils.translation import gettext_lazy as _
from dsfr.constants import COLOR_CHOICES_ILLUSTRATION, IMAGE_RATIOS
from wagtail import blocks
from wagtail.blocks import StructValue
from wagtail.images import get_image_model
from wagtail.images.blocks import ImageBlock, ImageChooserBlock
from wagtail.snippets.blocks import SnippetChooserBlock

from sites_conformes.content_manager.blocks.badges_tags import TagListBlock
from sites_conformes.content_manager.constants import (
    ALIGN_HORIZONTAL_CHOICES,
    ALIGN_HORIZONTAL_CHOICES_EXTENDED,
    ALIGN_VERTICAL_CHOICES,
    HEADING_CHOICES,
    LEVEL_CHOICES,
    LIMITED_RICHTEXTFIELD_FEATURES,
    MEDIA_WIDTH_CHOICES,
    TEXT_SIZE_CHOICES,
)

from .buttons_links import (
    ButtonBlock,
    ButtonsHorizontalListBlock,
    IconPickerBlock,
    LinkWithoutLabelBlock,
    SingleLinkBlock,
)

Image = get_image_model()

# Wagtail Block Documentation : https://docs.wagtail.org/en/stable/reference/streamfield/blocks.html


## Basic blocks
class TextContentBlock(blocks.StructBlock):
    hero_title = blocks.CharBlock(
        label=_("Title header"),
        required=False,
        help_text=_(
            "The title that will appear in the header of your page. If there is no header, the page title will appear."
        ),
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
    position = blocks.ChoiceBlock(
        choices=ALIGN_HORIZONTAL_CHOICES,
        label=_("Text content position"),
        default="left",
        help_text=_("This field allows you to define the placement of text relative to adjacent content."),
    )


class TextContentAllAlignments(TextContentBlock):
    position = blocks.ChoiceBlock(
        choices=ALIGN_HORIZONTAL_CHOICES_EXTENDED,
        label=_("Text content position"),
        default="",
        required=False,
        help_text=_("This field allows you to define the placement of text."),
    )


class TextContentVerticalAlignments(TextContentBlock):
    position = blocks.ChoiceBlock(
        choices=ALIGN_VERTICAL_CHOICES,
        label=_("Text content position"),
        default="bottom",
        help_text=_(
            "This field allows you to define the placement of text relative to adjacent content in vertical position."
        ),
    )


class AccordionBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Title"))
    content = blocks.RichTextBlock(label=_("Content"))


class AccordionsBlock(blocks.StreamBlock):
    title = blocks.CharBlock(label=_("Title"))
    accordion = AccordionBlock(label=_("Accordion"), min_num=1, max_num=15)

    class Meta:
        template = "sites_conformes_content_manager/blocks/accordions.html"


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
        template = "sites_conformes_content_manager/blocks/alert.html"


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
        template = "sites_conformes_content_manager/blocks/callout.html"


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
        template = "sites_conformes_content_manager/blocks/highlight.html"


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

    class Meta:
        icon = "image"
        template = "sites_conformes_content_manager/blocks/image_and_text.html"


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
        template = "sites_conformes_content_manager/blocks/image.html"
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
        template = "sites_conformes_content_manager/blocks/quote.html"


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
        template = "sites_conformes_content_manager/blocks/stepper.html"


class TextAndCTA(blocks.StructBlock):
    text = blocks.RichTextBlock(label=_("Rich text"), required=False)
    cta_buttons = blocks.StreamBlock(
        [
            (
                "buttons",
                ButtonsHorizontalListBlock(
                    help_text=_("""Please use only one primary button.
                        If you use icons, use them on all buttons and align them on the same side."""),
                    label=_("Buttons"),
                ),
            ),
        ],
        label=_("Call-to-action buttons"),
        max_num=1,
        required=False,
    )

    class Meta:
        icon = "link"
        template = "sites_conformes_content_manager/blocks/text_and_cta.html"


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
        "sites_conformes_blog.Person",
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
        template = ("sites_conformes_content_manager/blocks/contact_card_vertical.html",)
