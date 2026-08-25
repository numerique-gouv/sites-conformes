from django.utils.translation import gettext_lazy as _
from wagtail import blocks
from wagtailmarkdown.blocks import MarkdownBlock

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
)
from .buttons_links import AnchorBlock, ButtonsListBlock, SingleLinkBlock
from .cards import HorizontalCardBlock, TileBlock
from .heros import HeroBackgroundImageBlock, HeroImageAndTextBlock, HeroWideImageAndTextBlock, OldHero
from .layout import (
    FullWidthBackgroundBlock,
    FullWidthBackgroundWithSidemenuBlock,
    ItemGridBlock,
    MultiColumnsWithTitleBlock,
    TabsBlock,
)
from .medias import IframeBlock, TranscriptionBlock, VideoBlock
from .related_entries import BlogRecentEntriesBlock, EventsRecentEntriesBlock
from .sections import (
    AccordionSection,
    CTASection,
    ImageAndTextGridSection,
    ImageTextCTASection,
    ResizedTextSection,
    SpotlightSection,
)
from .tables import AdvancedTypedTableBlock

## Streamblocks definitions
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
    (
        "layout_richtext",
        ResizedTextSection(label=_("Rich text with layout"), group=_("Section templates to be adapted")),
    ),
    (
        "image_text_grid_section",
        ImageAndTextGridSection(label=_("Items grid (image and text)"), group=_("Section templates to be adapted")),
    ),
    (
        "image_text_cta_section",
        ImageTextCTASection(label=_("Image, text and cta"), group=_("Section templates to be adapted")),
    ),
    ("cta_section", CTASection(label=_("Text and button"), group=_("Section templates to be adapted"))),
    (
        "spotlight_section",
        SpotlightSection(label=_("In the spotlight"), group=_("Section templates to be adapted")),
    ),
    (
        "accordion_section",
        AccordionSection(label=_("Accordions with layout"), group=_("Section templates to be adapted")),
    ),
    ("accordions", AccordionsBlock(label=_("Accordions"), group=_("DSFR components"))),
    ("callout", CalloutBlock(label=_("Callout"), group=_("DSFR components"))),
    ("highlight", HighlightBlock(label=_("Highlight"), group=_("DSFR components"))),
    ("quote", QuoteBlock(label=_("Quote"), group=_("DSFR components"))),
    ("stepper", StepperBlock(label=_("Stepper"), group=_("DSFR components"))),
    ("card", HorizontalCardBlock(label=_("Horizontal card"), group=_("DSFR components"))),
    ("tile", TileBlock(label=_("Tile"), group=_("DSFR components"))),
    ("tabs", TabsBlock(label=_("Tabs"), group=_("DSFR components"))),
    ("anchor", AnchorBlock(label=_("Anchor"), group=_("Page structure"))),
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
            template="sites_conformes_core/blocks/subpages_list.html",
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
]


HERO_STREAMFIELD_BLOCKS = [
    ("hero_text_image", HeroImageAndTextBlock(label=_("Header with an image and text"))),
    ("hero_text_wide_image", HeroWideImageAndTextBlock(label=_("Vertical header with a banner and text"))),
    ("hero_text_background_image", HeroBackgroundImageBlock(label=_("Header with background"))),
    ("old_hero", OldHero(label=_("Configurable header"))),
]
