from urllib.parse import urlencode

from django import template

register = template.Library()

FilterSpec = tuple[str, str]

PUBLICATION_INDEX_FILTERS: list[FilterSpec] = [
    ("author", "id"),
    ("collection", "slug"),
    ("theme", "slug"),
    ("source", "slug"),
    ("tag", "slug"),
    ("year", ""),
]


def build_toggle_url_query_string(context, filters: list[FilterSpec], **kwargs) -> str:
    """
    Set or remove a filter query param (toggle off when already active).

    ``kwargs`` are filter values from the template (e.g. collection=collection).
    Optional ``filters_dict`` overrides ``request.GET`` as the starting query params.
    """
    filters_dict = kwargs.pop("filters_dict", None)
    if filters_dict:
        base_params = filters_dict.copy()
    else:
        base_params = context["request"].GET.copy()

    for param, attr in filters:
        val = kwargs.get(param, "")
        current_val = context.get(f"current_{param}", "")

        if val and val != current_val:
            if attr:
                base_params[param] = getattr(val, attr)
            else:
                base_params[param] = val
        elif val and val == current_val:
            base_params.pop(param, None)

    url_string = urlencode(base_params, doseq=True)
    if url_string:
        return f"?{url_string}"
    return ""


@register.simple_tag(takes_context=True)
def toggle_url_filter(context, *_, **kwargs):
    """
    Sets a URL filter, or removes it if it is already in use.

    Same behaviour as sites_conformes.core.templatetags.wagtail_dsfr_tags.toggle_url_filter,
    with collection and theme query parameters.
    """
    return build_toggle_url_query_string(context, PUBLICATION_INDEX_FILTERS, **kwargs)
