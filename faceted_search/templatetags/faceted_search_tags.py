from django import template

from sites_conformes.core.templatetags.wagtail_dsfr_tags import (
    FilterSpec,
    build_toggle_url_query_string,
)

register = template.Library()

SEARCH_FILTERS: list[FilterSpec] = [
    ("author", "id"),
    ("category", "slug"),
    ("collection", "slug"),
    ("theme", "slug"),
    ("source", "slug"),
    ("tag", "slug"),
    ("year", ""),
]


@register.simple_tag(takes_context=True)
def toggle_url_filter(context, *_, **kwargs):
    """``toggle_url_filter`` for the search page (preserves ``q`` and other GET params)."""
    return build_toggle_url_query_string(context, SEARCH_FILTERS, **kwargs)
