from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from publications.models import Collection, Theme


class CollectionViewSet(SnippetViewSet):
    model = Collection
    icon = "folder-open-inverse"  # type: ignore


class ThemeViewSet(SnippetViewSet):
    model = Theme
    icon = "tag"  # type: ignore


class PublicationsTaxonomyViewSetGroup(SnippetViewSetGroup):
    items = (CollectionViewSet, ThemeViewSet)
    menu_icon = "doc-full-inverse"
    menu_label = "Publications"  # type: ignore
    menu_name = "publications_taxonomy"
    menu_order = 8300


register_snippet(PublicationsTaxonomyViewSetGroup)
