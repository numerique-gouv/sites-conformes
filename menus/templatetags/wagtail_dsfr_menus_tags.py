from django import template
from django.template.context import Context
from wagtail.models import Locale, Site

from menus.models import FooterBottomMenu, MainMenu, TopMenu

register = template.Library()


@register.inclusion_tag("menus/header_top_menu.html", takes_context=True)
def top_menu(context: Context) -> dict:
    """
    Returns the top_menu item for the site
    """
    request = context.get("request", None)
    site = Site.find_for_request(request)

    locale = Locale.get_active()
    top_menu = TopMenu.objects.filter(site=site, locale=locale).first() or TopMenu.objects.filter(site=site).first()

    current_page = context.get("page", None)

    return {"request": request, "top_menu": top_menu, "current_page": current_page}


@register.inclusion_tag("menus/footer_bottom_menu.html", takes_context=True)
def footer_bottom_menu(context: Context) -> dict:
    """
    Returns the footer_bottom_menu item for the site
    """
    request = context.get("request", None)
    site = Site.find_for_request(request)

    locale = Locale.get_active()
    footer_bottom_menu = (
        FooterBottomMenu.objects.filter(site=site, locale=locale).first()
        or FooterBottomMenu.objects.filter(site=site).first()
    )

    current_page = context.get("page", None)

    return {"request": request, "footer_bottom_menu": footer_bottom_menu, "current_page": current_page}


@register.inclusion_tag("menus/header_main_menu.html", takes_context=True)
def main_menu(context: Context) -> dict:
    """
    Returns the main_menu item for the site
    """
    request = context.get("request", None)
    site = Site.find_for_request(request)

    locale = Locale.get_active()
    main_menu = MainMenu.objects.filter(site=site, locale=locale).first() or MainMenu.objects.filter(site=site).first()

    current_page = context.get("page", None)

    return {"request": request, "main_menu": main_menu, "current_page": current_page}
