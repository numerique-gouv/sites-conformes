from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from sites_conformes.core.multisite_isolation import SiteScopedViewSetMixin
from sites_conformes.menus.models import FooterBottomMenu, MainMenu, TopMenu


class TopMenuViewSet(SiteScopedViewSetMixin, SnippetViewSet):
    model = TopMenu
    icon = "minus"  # type: ignore


class FooterBottomMenuViewSet(SiteScopedViewSetMixin, SnippetViewSet):
    model = FooterBottomMenu
    icon = "minus"  # type: ignore


class MainMenuViewSet(SiteScopedViewSetMixin, SnippetViewSet):
    model = MainMenu
    icon = "minus"  # type: ignore


class MenusViewSetGroup(SnippetViewSetGroup):
    items = (TopMenuViewSet, MainMenuViewSet, FooterBottomMenuViewSet)
    menu_icon = "bars"
    menu_label = "Menus"  # type: ignore
    menu_name = "menus"
    menu_order = 8400


register_snippet(MenusViewSetGroup)
