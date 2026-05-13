from django.utils.translation import gettext_lazy as _
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock

from sites_conformes.content_manager.blocks.basics import ImageAndTextBlock, QuoteBlock
from sites_conformes.content_manager.blocks.layout import MultiColumnsWithTitleBlock


class ContactCardBlock(blocks.StructBlock):
    name = blocks.CharBlock(label=_("Name"), max_length=255)
    role = blocks.CharBlock(label=_("Role"), max_length=255)
    organization = blocks.CharBlock(label=_("Organization"), max_length=255)
    contact_info = blocks.CharBlock(label=_("Contact info"), max_length=500, required=False)
    image = ImageChooserBlock(label="Image")

    class Meta:
        icon = "user"
        template = ("sites_conformes_blog/blocks/contact_card.html",)


COLOPHON_BLOCKS = [
    ("paragraph", blocks.RichTextBlock(label=_("Rich text"))),
    (
        "imageandtext",
        ImageAndTextBlock(label="Bloc image et texte"),
    ),
    ("quote", QuoteBlock(label="Citation")),
    ("multicolumns", MultiColumnsWithTitleBlock(label="Multi-colonnes")),
    ("contact_card", ContactCardBlock(label=_("Contact card"))),
]
