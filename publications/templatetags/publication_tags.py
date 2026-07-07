from urllib.parse import urlencode

from django import template

from sites_conformes.core.templatetags.wagtail_dsfr_tags import (
    FilterSpec,
    build_toggle_url_query_string,
)

register = template.Library()

PUBLICATION_FILTERS: list[FilterSpec] = [
    ("author", "id"),
    ("collection", "slug"),
    ("theme", "slug"),
    ("source", "slug"),
    ("tag", "slug"),
    ("year", ""),
]


@register.simple_tag(takes_context=True)
def toggle_url_filter(context, *_, **kwargs):
    """Blog ``toggle_url_filter`` with collection and theme query parameters."""
    return build_toggle_url_query_string(context, PUBLICATION_FILTERS, **kwargs)


@register.simple_tag
def filters_query(filters_dict=None):
    """Build a ``?key=val`` query string from publication index filter params."""
    if not filters_dict:
        return ""
    url_string = urlencode(filters_dict, doseq=True)
    return f"?{url_string}" if url_string else ""
