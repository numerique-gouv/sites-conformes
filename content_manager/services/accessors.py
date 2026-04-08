import sys

from django.core.management.color import color_style
from django.utils.translation import gettext_lazy as _
from wagtail.models import Collection, Page, PageViewRestriction

from content_manager.constants import HEADER_FIELDS
from content_manager.models import CatalogIndexPage, ContentPage
from content_manager.utils import get_default_site
from menus.models import FooterBottomMenu, MainMenu

style = color_style()

"""
Methods to get or create various type of contents.
Moved from utils to avoid circular module dependencies.
"""


def get_or_create_collection(col_name: str) -> Collection:
    qs = Collection.objects.filter(name=col_name)
    if qs.count():
        return qs.first()  # type: ignore
    else:
        root_coll = Collection.get_first_root_node()
        result = root_coll.add_child(name=col_name)
        return result


def get_or_create_catalog_index_page(
    slug: str,
    title: str,
    body: list,
    parent_page: Page | ContentPage | None = None,
    restriction_type: str | None = None,
    page_fields: dict | None = None,
) -> CatalogIndexPage:
    """
    Get a CatalogIndexPage if it exists, or creates it instead.
    """

    site = get_default_site()
    root_page = site.root_page
    locale = root_page.locale

    if parent_page:
        if not isinstance(parent_page, (Page, ContentPage)):
            # Default "Page" type is allowed to allow the default root page"
            raise TypeError("The parent page should be a content page.")
    else:
        # If parent_page is not passed as parameter, use the Home page of the default site.
        if not isinstance(root_page, (Page, ContentPage)):
            raise TypeError("The parent page should be a content page.")
        parent_page = root_page

    # Don't replace or duplicate an already existing page
    already_exists = CatalogIndexPage.objects.filter(slug=slug, locale=locale).first()
    if already_exists:
        sys.stdout.write(f"The {slug} page seem to already exist with id {already_exists.id}\n")
        return already_exists

    new_page = parent_page.add_child(
        instance=CatalogIndexPage(
            title=title,
            body=body,
            slug=slug,
            show_in_menus=True,
        )
    )

    allowed_page_fields = HEADER_FIELDS + ["source_url"]
    if page_fields and len(page_fields):
        for k, v in page_fields.items():
            if k in allowed_page_fields:
                setattr(new_page, k, v)
        new_page.save()

    if restriction_type:
        PageViewRestriction.objects.create(page=new_page, restriction_type=restriction_type)

    sys.stdout.write(style.SUCCESS(f"Page {slug} created with id {new_page.id}"))

    return new_page


def get_or_create_content_page(
    slug: str,
    title: str,
    body: list,
    parent_page: Page | ContentPage | CatalogIndexPage | None = None,
    restriction_type: str | None = None,
    page_fields: dict | None = None,
) -> ContentPage:
    """
    Get a ContentPage if it exists, or creates it instead.
    """

    site = get_default_site()
    root_page = site.root_page
    locale = root_page.locale

    if parent_page:
        if not isinstance(parent_page, (Page, ContentPage, CatalogIndexPage)):
            # Default "Page" type is allowed to allow the default root page"
            raise TypeError("The parent page should be a content page or a catalog index page.")
    else:
        # If parent_page is not passed as parameter, use the Home page of the default site.
        if not isinstance(root_page, (Page, ContentPage, CatalogIndexPage)):
            raise TypeError("The parent page should be a content page or a catalog index page.")
        parent_page = root_page

    # Don't replace or duplicate an already existing page
    already_exists = ContentPage.objects.filter(slug=slug, locale=locale).first()
    if already_exists:
        sys.stdout.write(f"The {slug} page seem to already exist with id {already_exists.id}\n")
        return already_exists

    new_page = parent_page.add_child(
        instance=ContentPage(
            title=title,
            body=body,
            slug=slug,
            show_in_menus=True,
        )
    )

    allowed_page_fields = HEADER_FIELDS + ["source_url"]
    if page_fields and len(page_fields):
        for k, v in page_fields.items():
            if k in allowed_page_fields:
                setattr(new_page, k, v)
        new_page.save()

    if restriction_type:
        PageViewRestriction.objects.create(page=new_page, restriction_type=restriction_type)

    sys.stdout.write(style.SUCCESS(f"Page {slug} created with id {new_page.id}"))

    return new_page


def get_or_create_footer_bottom_menu() -> FooterBottomMenu:
    """
    Get the footer menu or create it if it doesn't already exist

    In any case, return it.
    """

    default_site = get_default_site()
    root_page = default_site.root_page
    locale = root_page.locale

    footer_menu, _created = FooterBottomMenu.objects.get_or_create(site=default_site, locale=locale)

    return footer_menu


def get_or_create_main_menu() -> MainMenu:
    """
    Get the main menu or create it if it doesn't already exist

    In any case, return it.
    """

    default_site = get_default_site()
    root_page = default_site.root_page
    locale = root_page.locale

    main_menu, created = MainMenu.objects.get_or_create(site=default_site, locale=locale)

    if created:
        # Add a link to the home page by default
        link_value = {
            "text": _("Home page"),
            "page": root_page,
            "link_type": "page",
        }
        main_menu.items.append(("link", link_value))

    main_menu.save()
    return main_menu
