from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from wagtail.blocks import CharBlock, ChoiceBlock, StreamBlock, StructBlock, StructValue

from content_manager.blocks import IconPickerBlock, LinkStructValue, LinkWithoutLabelBlock


class BaseMenuLinkBlock(LinkWithoutLabelBlock):
    # Menus are used on the whole site, so disable anchored link to the current page
    LINK_TYPE_CHOICES = [
        ("page", _("Page")),
        ("external_url", _("External URL")),
        ("document", _("Document")),
    ]
    link_type = ChoiceBlock(
        choices=LINK_TYPE_CHOICES,
        required=False,
        label=_("Link type"),
        help_text=_("Select the type of link."),
    )

    text = CharBlock(
        label=_("Link label"),
        required=False,
        help_text=_("If this field is empty, the title of the linked page or document will be used."),
    )

    class Meta:
        value_class = LinkStructValue
        icon = "link"
        template = "menus/blocks/link.html"


class MenuLinkWithIconBlock(BaseMenuLinkBlock):
    icon_class = IconPickerBlock(label=_("Icon"), required=False)


class FooterBottomLinkBlock(BaseMenuLinkBlock):
    class Meta:
        template = "menus/blocks/footer_bottom_link.html"


class MainMenuLinkBlock(BaseMenuLinkBlock):
    class Meta:
        template = "menus/blocks/main_menu_link.html"


class MainMenuSubmenuLinkBlock(BaseMenuLinkBlock):
    class Meta:
        template = "menus/blocks/main_menu_link.html"


class MainMenuMegamenuMainLinkBlock(BaseMenuLinkBlock):
    text = CharBlock(
        label=_("Link label"),
        default=_("See the whole section"),
    )

    class Meta:
        template = "menus/blocks/main_menu_link.html"


class MainMenuStructValue(StructValue):
    def id(self):
        label = self.get("label", "")
        raw_id = slugify(label)
        return f"collapse-menu-{raw_id}"

    def menu_urls(self):
        links = self.get("links", [])
        columns = self.get("columns", [])

        urls = []

        if links:
            for link in links:
                urls.append(link.value.url())

        if columns:
            for column in columns:
                column_links = column.value.get("links", [])
                for link in column_links:
                    urls.append(link.value.url())

        return urls


class MainMenuSubmenuBlock(StructBlock):
    label = CharBlock(
        label=_("Submenu label"),
        required=True,
    )

    links = StreamBlock(
        [
            ("link", MainMenuSubmenuLinkBlock()),
        ],
        label=_("Links"),
        min_num=1,
        help_text=_("The recommended maximum number of links in a single submenu is 8."),
    )

    class Meta:
        template = "menus/blocks/main_menu_submenu.html"
        value_class = MainMenuStructValue


class MainMenuMegamenuColumnBlock(MainMenuSubmenuBlock):
    label = CharBlock(
        label=_("Column label"),
        required=True,
    )

    class Meta:
        template = "menus/blocks/main_menu_megamenu_column.html"
        value_class = MainMenuStructValue


class MainMenuMegamenuBlock(StructBlock):
    label = CharBlock(
        label=_("Mega menu label"),
        required=True,
    )

    description = CharBlock(
        label=_("Description"),
        required=False,
    )

    main_link = MainMenuMegamenuMainLinkBlock(
        label=_("Main link"),
        required=False,
    )

    columns = StreamBlock(
        [
            ("column", MainMenuMegamenuColumnBlock(label=_("Column"))),
        ],
        label=_("Columns"),
        min_num=1,
        max_num=4,
        required=True,
    )

    class Meta:
        template = "menus/blocks/main_menu_megamenu.html"
        value_class = MainMenuStructValue


TOP_MENU_BLOCKS = [
    ("link", MenuLinkWithIconBlock(label=_("Link"))),
]

FOOTER_BOTTOM_MENU_BLOCKS = [
    ("link", FooterBottomLinkBlock(label=_("Link"))),
]

MAIN_MENU_BLOCKS = [
    ("link", MainMenuLinkBlock(label=_("Link"))),
    ("submenu", MainMenuSubmenuBlock(label=_("Submenu"))),
    ("megamenu", MainMenuMegamenuBlock(label=_("Mega menu"))),
]
