from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import escape, format_html
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.ui.components import Component
from wagtail.rich_text import LinkHandler

from sites_conformes import __version__
from sites_conformes.dashboard.views import NotificationPanel, ShortcutsPanel, TutorialsPanel


@hooks.register("insert_global_admin_css")
def global_admin_css():
    # On charge uniquement le CSS du composant Notice du DSFR (et non dsfr.min.css complet, qui casserait
    # le style du back-office Wagtail). Ce fichier ne cible que les classes .fr-notice*.
    return format_html(
        '\n<link rel="stylesheet" href="{}">\n<link rel="stylesheet" href="{}">',
        static("dsfr/dist/component/notice/notice.min.css"),
        static("css/admin.css"),
    )


@hooks.register("construct_help_menu")
def add_version_help_menu_item(request, menu_items):
    menu_items.append(
        MenuItem(
            _("Sites Conformes %(version)s") % {"version": __version__},
            settings.RELEASES_URL,
            icon_name="help",
            attrs={"target": "_blank", "rel": "noopener noreferrer"},
            order=1000,
        )
    )


@hooks.register("register_icons")
def register_icons(icons):
    return icons + ["admin_icons/anchor.svg"]


@hooks.register("insert_editor_js")
def insert_custom_editor_scripts():
    return format_html(
        """
        <script src="{}"></script>
        <script src="{}"></script>
        <script src="{}"></script>
        """,
        static("js/admin_editor.js"),
        static("js/open_preview_panel.js"),
        static("js/language-selector-admin.js"),
    )


@hooks.register("register_admin_menu_item")
def register_site_menu_item():
    index_url = f"{settings.FORCE_SCRIPT_NAME or ''}/"
    return MenuItem(
        _("Visit site"),
        index_url,
        icon_name="home",
        order=0,
    )


class UserbarPageAPILinkItem(Component):
    """
    When on a Wagtail page, add a link to the Page API for admin users in the wagtail toolbar
    """

    def render_html(self, parent_context) -> str:
        request = parent_context["request"]  # type: ignore
        if hasattr(request, "_wagtail_route_for_request") and hasattr(request._wagtail_route_for_request, "page"):
            page = request._wagtail_route_for_request.page
            page_url = reverse("wagtailapi:pages:detail", kwargs={"pk": page.id})
            page_in_api_label = _("See page entry in API")
            if page and request.user.has_perm("wagtailadmin.access_admin"):
                return f"""<li class="w-userbar__item " role="presentation">
                            <a href="{page_url}" target="_parent" role="menuitem" tabindex="-1">
                                <svg class="icon icon-crosshairs w-action-icon" aria-hidden="true">
                                    <use href="#icon-crosshairs"></use>
                                </svg> {page_in_api_label}
                            </a>
                        </li>"""
        return ""


@hooks.register("construct_wagtail_userbar")
def add_page_api_link_item(request, items, page):
    return items.append(UserbarPageAPILinkItem())


class NewWindowExternalLinkHandler(LinkHandler):
    identifier = "external"

    @classmethod
    def expand_db_attributes(cls, attrs):
        href = attrs["href"]
        # Let's add the target attr, and also rel="noopener" + noreferrer fallback.
        # See https://github.com/whatwg/html/issues/4078.
        new_window = _("(Opens a new window)")
        return f"""<a href="{escape(href)}" target="_blank" rel="noopener noreferrer">
                <span class="fr-sr-only">{new_window}</span> """


@hooks.register("register_rich_text_features")
def register_external_link(features):
    features.register_link_type(NewWindowExternalLinkHandler)


@hooks.register("construct_homepage_summary_items", order=1)
def remove_all_summary_items(request, items):
    items.clear()


@hooks.register("construct_homepage_panels")
def add_shortcuts_panel(request, panels):
    panels.insert(0, NotificationPanel())
    panels.append(ShortcutsPanel())
    if not settings.SF_DISABLE_TUTORIALS:
        panels.append(TutorialsPanel())
