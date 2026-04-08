from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from proconnect.models import WhitelistedEmailDomain


class WhitelistedEmailDomainViewSet(SnippetViewSet):
    model = WhitelistedEmailDomain
    icon = "mail"  # type: ignore
    admin_url_namespace = "member_views"


class ProconnectViewSetGroup(SnippetViewSetGroup):
    items = (WhitelistedEmailDomainViewSet,)
    menu_icon = "group"
    menu_label = "ProConnect"  # type: ignore
    menu_name = "proconnect"
    menu_order = 8500


register_snippet(ProconnectViewSetGroup)
