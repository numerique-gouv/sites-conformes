from bs4 import BeautifulSoup
from django import template
from django.conf import settings
from django.template.context import Context
from django.utils.html import mark_safe
from wagtail.models import Site
from wagtail.rich_text import RichText

from sites_conformes.core.models import CmsDsfrConfig

register = template.Library()


@register.simple_tag
def settings_value(name):
    return getattr(settings, name, "")


@register.simple_tag
def root_url() -> str:
    """Return the site's base path, taking FORCE_SCRIPT_NAME into account."""
    return f"{settings.FORCE_SCRIPT_NAME}/"


@register.simple_tag(takes_context=True)
def canonical_url(context):
    """
    Make the best effort to get a canonical URL for the current page, considering that:
    - Multiple schemes can be allowed (http vs https), but only one should be canonical
    - Sites can answer to multiple URLs, but only one should be canonical
    - Multiple sites can exist on the same instance
    - Some pages are not instances of Wagtail Pages (eg. search results, 404, etc.)
    """
    request = context.get("request", None)
    if not request:
        # For the error 500 page
        return ""

    scheme = settings.HOST_PROTO
    site = Site.find_for_request(request)

    if site:
        hostname = site.hostname
        if site.port != 80:
            hostname = f"{hostname}:{site.port}"
    else:
        hostname = request.get_host()

    return f"{scheme}://{hostname}{request.path}"


@register.inclusion_tag("sites_conformes_core/widgets/language_selector.html", takes_context=True)
def language_selector(context: Context) -> dict:
    """
    Returns the language selector item.
    """
    request = context.get("request", None)

    cms_settings = CmsDsfrConfig.for_request(request)

    mode = cms_settings.language_selector_mode

    if mode == "simple":
        is_active = True
        site = Site.find_for_request(request)

        homepage = site.root_page
        default_locale = homepage.locale

        language_selector_items = [
            {
                "language_code": default_locale.language_code,
                "language_name": default_locale.language_name_localized,
                "url": homepage.get_full_url(request=request),
            }
        ]

        for t in homepage.get_translations():
            language_selector_items.append(
                {
                    "language_code": t.locale.language_code,
                    "language_name": t.locale.language_name_localized,
                    "url": t.get_full_url(request=request),
                }
            )
    elif mode == "manual":
        is_active = True
        items = cms_settings.language_selector_items.all()

        language_selector_items = []

        for i in items:
            if i.page:
                language_selector_items.append(
                    {
                        "language_code": i.language_code,
                        "language_name": i.language_name,
                        "url": i.page.full_url,
                    }
                )
            else:
                language_selector_items.append(
                    {
                        "language_code": i.language_code,
                        "language_name": i.language_name,
                        "url": i.external_url,
                    }
                )
    else:
        is_active = False
        language_selector_items = []

    language_selector = {"is_active": is_active, "items": language_selector_items}

    return {"request": context["request"], "language_selector": language_selector}


@register.filter
def richtext_p_add_class(value, class_name: str):
    """
    Adds a CSS class to a Richtext-generated paragraph.

    Intended to be used right after a `| richext` filter in case of a RichTextField
    (not necessary for a RichTextBlock)
    """

    if not class_name:
        return value

    if isinstance(value, RichText):
        # In case of a RichTextBlock, first render it
        value = str(value)

    soup = BeautifulSoup(value, "html.parser")

    paragraphs = soup.find_all("p")

    for p in paragraphs:
        p["class"] = p.get("class", []) + [class_name]  # type: ignore

    return mark_safe(str(soup))


@register.simple_tag(takes_context=True)
def toggle_url_filter(context, *_, **kwargs):
    """
    Sets a URL filter, or removes it if it is already in use.

    The other filters can be passed through a dictionary or the GET parameters
    """

    filters_dict = kwargs.get("filters_dict", {})
    if filters_dict:
        url_params = filters_dict.copy()
    else:
        url_params = context["request"].GET.copy()

    filters = [("author", "id"), ("category", "slug"), ("source", "slug"), ("tag", "slug"), ("year", "")]

    for f in filters:
        param = f[0]
        attr = f[1]
        val = kwargs.get(param, "")
        current_val = context.get(f"current_{param}", "")

        if val and val != current_val:
            if attr:
                url_params[param] = getattr(val, attr)
            else:
                url_params[param] = val
        elif val and val == current_val:
            url_params.pop(param, None)

    url_string = "&".join(["{}={}".format(x[0], x[1]) for x in url_params.items()])

    if url_string:
        return f"?{url_string}"
    else:
        return ""


@register.filter
def table_has_heading_row(value):
    non_empty_heading = False
    for col in value:
        if col["heading"]:
            non_empty_heading = True
    return non_empty_heading
