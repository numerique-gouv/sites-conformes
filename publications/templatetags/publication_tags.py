from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def toggle_url_filter(context, *_, **kwargs):
    """
    Sets a URL filter, or removes it if it is already in use.

    Same behaviour as sites_conformes.core.templatetags.wagtail_dsfr_tags.toggle_url_filter,
    with collection and theme query parameters.
    """

    filters_dict = kwargs.get("filters_dict", {})
    if filters_dict:
        url_params = filters_dict.copy()
    else:
        url_params = context["request"].GET.copy()

    filters = [
        ("author", "id"),
        ("collection", "slug"),
        ("theme", "slug"),
        ("source", "slug"),
        ("tag", "slug"),
        ("year", ""),
    ]

    for param, attr in filters:
        val = kwargs.get(param, "")
        current_val = context.get(f"current_{param}", "")

        if val and val != current_val:
            if attr:
                url_params[param] = getattr(val, attr)
            else:
                url_params[param] = val
        elif val and val == current_val:
            url_params.pop(param, None)

    url_string = "&".join(["{}={}".format(key, value) for key, value in url_params.items()])

    if url_string:
        return f"?{url_string}"
    return ""
