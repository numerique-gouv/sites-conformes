from django.utils.translation import gettext_lazy as _

from publications.models import Collection, Theme
from sites_conformes.blog.taxonomy import Taxonomy

COLLECTION = Taxonomy(
    slug="collection",
    model=Collection,
    m2m_field="collections",
    filter_field="filter_by_collection",
    filter_heading=_("Filter by collection"),
    list_label_plural=_("Collections"),
    list_route_name="collections_list",
    list_template="publications/collections_list_page.html",
    list_prefix="coll",
    list_context_key="collections",
    current_context_key="current_collection",
    filtered_title=_("Posts in collection %(collection)s"),
    filtered_title_param="collection",
)

THEME = Taxonomy(
    slug="theme",
    model=Theme,
    m2m_field="themes",
    filter_field="filter_by_theme",
    filter_heading=_("Filter by theme"),
    list_label_plural=_("Themes"),
    list_route_name="themes_list",
    list_template="publications/themes_list_page.html",
    list_prefix="theme",
    list_context_key="themes",
    current_context_key="current_theme",
    filtered_title=_("Posts in theme %(theme)s"),
    filtered_title_param="theme",
)
