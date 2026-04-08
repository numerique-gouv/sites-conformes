from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from menus.models import FooterBottomMenu, MainMenu, TopMenu


class TopMenuViewSet(SnippetViewSet):
    model = TopMenu
    icon = "minus"  # type: ignore


class FooterBottomMenuViewSet(SnippetViewSet):
    model = FooterBottomMenu
    icon = "minus"  # type: ignore


class MainMenuViewSet(SnippetViewSet):
    model = MainMenu
    icon = "minus"  # type: ignore


class MenusViewSetGroup(SnippetViewSetGroup):
    items = (TopMenuViewSet, MainMenuViewSet, FooterBottomMenuViewSet)
    menu_icon = "bars"
    menu_label = "Menus"  # type: ignore
    menu_name = "menus"
    menu_order = 8400


register_snippet(MenusViewSetGroup)
