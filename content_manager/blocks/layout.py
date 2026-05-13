from django.utils.translation import gettext_lazy as _
from dsfr.constants import COLOR_CHOICES
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock
from wagtailmarkdown.blocks import MarkdownBlock

from sites_conformes.content_manager.constants import (
    GRID_3_4_6_CHOICES,
    GRID_HORIZONTAL_ALIGN_CHOICES,
    GRID_VERTICAL_ALIGN_CHOICES,
    HEADING_CHOICES,
)

from .badges_tags import BadgesListBlock, TagListBlock
from .basics import (
    AccordionsBlock,
    AlertBlock,
    CalloutBlock,
    CenteredImageBlock,
    HighlightBlock,
    ImageAndTextBlock,
    QuoteBlock,
    SeparatorBlock,
    StepperBlock,
    TextAndCTA,
    VerticalContactCardBlock,
)
from .buttons_links import AnchorBlock, ButtonsListBlock, SingleLinkBlock
from .cards import HorizontalCardBlock, TileBlock, VerticalCardBlock
from .medias import IframeBlock, TranscriptionBlock, VideoBlock
from .related_entries import BlogRecentEntriesBlock, EventsRecentEntriesBlock
from .tables import AdvancedTypedTableBlock


class BackgroundColorChoiceBlock(blocks.ChoiceBlock):
    choices = COLOR_CHOICES

    class Meta:
        icon = "view"


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


class BackgroundColorBlock(blocks.StructBlock):
    background_color = BackgroundColorChoiceBlock(
        label=_("Background color"),
        required=False,
        help_text=_(
            "Uses the French Design System colors.<br>"
            "If you want to design a classic website, choose the colour ‘white’ or ‘French blue’."
        ),
    )


class LayoutBlock(MarginBlock, BackgroundColorBlock):

    class Meta:
        help_text = _("This part allow you to choose the layout of your block (background, margin..) ")


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
    anchor = AnchorBlock(label=_("Anchor"), group=_("Page structure"))
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
        template = "sites_conformes_content_manager/blocks/item_grid.html"
        value_class = GridPositionStructValue


class TabBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Title"))
    content = ColumnBlock(label=_("Content"))


class TabsBlock(blocks.StreamBlock):
    tabs = TabBlock(label=_("Tab"), min_num=1, max_num=15)

    class Meta:
        template = "sites_conformes_content_manager/blocks/tabs.html"


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
        template = "sites_conformes_content_manager/blocks/multicolumns.html"
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
        template = "sites_conformes_content_manager/blocks/full_width_background.html"
        value_class = BlockMarginStructValue


class PageTreeBlock(blocks.StructBlock):
    page = blocks.PageChooserBlock(label=_("Parent page"))

    class Meta:
        icon = "minus"
        template = "sites_conformes_content_manager/blocks/pagetree.html"


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
        template = "sites_conformes_content_manager/blocks/full_width_background_with_sidemenu.html"
        value_class = BlockMarginStructValue
