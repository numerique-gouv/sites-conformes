from django.utils.translation import gettext_lazy as _
from wagtail import blocks
from wagtail.contrib.typed_table_block.blocks import TypedTableBlock
from wagtail.images.blocks import ImageBlock

from sites_conformes.content_manager.constants import (
    LIMITED_RICHTEXTFIELD_FEATURES,
)


class PictogramBlock(ImageBlock):
    # A subclass of ImageBlock with the height fixed to 80px.
    class Meta:
        icon = "image"
        template = "sites_conformes_content_manager/widgets/pictogram.html"


class AdvancedTypedTableBlock(TypedTableBlock):
    row_heading = blocks.CharBlock(required=False, label=_("Row heading"))
    text = blocks.RichTextBlock(features=LIMITED_RICHTEXTFIELD_FEATURES, required=False, label=_("Text"))
    pictogram = PictogramBlock(required=False, label=_("Pictogram"))

    class Meta:
        icon = "table"
        template = "sites_conformes_content_manager/blocks/typed_table_block.html"
        help_text = _('The "row heading" column type only works on the first column of the table.')
