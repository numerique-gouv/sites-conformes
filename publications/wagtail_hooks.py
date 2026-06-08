from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from publications.models import Collection, Theme


class CollectionViewSet(SnippetViewSet):
    model = Collection
    icon = "folder-open-inverse"  # type: ignore


class ThemeViewSet(SnippetViewSet):
    model = Theme
    icon = "tag"  # type: ignore


register_snippet(CollectionViewSet)
register_snippet(ThemeViewSet)
