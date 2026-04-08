from django import forms
from django.core.validators import validate_slug
from django.forms.utils import ErrorList
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from wagtail import blocks
from wagtail.admin.telepath import register
from wagtail.blocks.struct_block import StructBlockAdapter, StructBlockValidationError
from wagtail.documents.blocks import DocumentChooserBlock

from content_manager.constants import (
    BUTTON_ICON_SIDE,
    BUTTON_TYPE_CHOICES,
    BUTTONS_ALIGN_CHOICES,
    LINK_ICON_CHOICES,
    LINK_SIZE_CHOICES,
)
from content_manager.validators import validate_query_string
from content_manager.widgets import DsfrIconPickerWidget


## Icon Picker
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


## Anchor
class AnchorBlock(blocks.StructBlock):
    anchor_id = blocks.CharBlock(
        label=_("Anchor ID"),
        help_text=_(
            "Allows the creation of a link to this specific part of the page. Allowed characters: A-Z, a-z, 0-9, - and _."  # noqa
        ),
        validators=[validate_slug],
    )

    class Meta:
        icon = "anchor"
        template = "content_manager/blocks/anchor.html"


## Buttons & Links
class LinkStructValue(blocks.StructValue):
    def url(self):
        link = self.get("external_url", "")

        page = self.get("page")
        document = self.get("document")
        anchor = self.get("anchor")
        query_string = self.get("query_string")

        if page:
            link = page.url
        elif document:
            link = document.url

        if anchor:
            link += f"#{anchor}"

        if query_string:
            link += f"{query_string}"

        return link

    def label(self):
        text = self.get("text", "")

        if not text:
            page = self.get("page")
            document = self.get("document")

            if page:
                text = page.title
            elif document:
                text = document.title

        return text


class LinkWithoutLabelBlock(blocks.StructBlock):
    LINK_TYPE_CHOICES = [
        ("page", _("Page")),
        ("external_url", _("External URL")),
        ("document", _("Document")),
        ("anchor", _("Anchor link")),
    ]

    link_type = blocks.ChoiceBlock(
        choices=LINK_TYPE_CHOICES,
        required=False,
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
    anchor = blocks.CharBlock(
        label=_("Anchor ID"),
        help_text=_("Link to an anchor block on the page. Allowed characters: A-Z, a-z, 0-9, - and _."),
        validators=[validate_slug],
        default="",
        required=False,
    )
    query_string = blocks.CharBlock(
        label=_("Extra query parameters"),
        help_text=_("Extra query parameters at the end of the link, e.g. filtering options."),
        validators=[validate_query_string],
        default="",
        required=False,
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
            # This is for backward compatibility: try to infer the link type
            for link_type in self.link_types:
                if value.get(link_type):
                    selected_link_type = link_type
                    value["link_type"] = link_type
                    break
        elif selected_link_type:
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

        for link_type in ["external_url", "document", "page"]:
            if link_type != selected_link_type:
                value[link_type] = None

        if selected_link_type in ["external_url", "document"]:
            value["anchor"] = ""

        if selected_link_type in ["external_url", "document", "anchor"]:
            value["query_string"] = ""

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
        help_text=_("""Please use only one primary button.
            If you use icons, use them on all buttons and align them on the same side."""),
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


class LinkBlockAdapter(StructBlockAdapter):
    js_constructor = "blocks.links.LinkBlock"

    def js_args(self, block):
        args = super().js_args(block)
        args[2]["link_types"] = block.link_types
        return args

    @cached_property
    def media(self):
        from django import forms

        structblock_media = super().media
        return forms.Media(
            js=structblock_media._js + ["js/link-block.js"],  # type: ignore
        )


register(LinkBlockAdapter(), LinkWithoutLabelBlock)
