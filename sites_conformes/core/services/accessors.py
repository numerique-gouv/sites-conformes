"""
Methods to get or create various type of contents (collections, pages, menus).
Moved from utils to avoid circular module dependencies.

They are mostly used by the management commands that create the starter and demo
contents, and are imported automatically in `python manage.py shell`.
They are idempotent: calling them twice doesn't create duplicates.
"""

import sys

import swapper
from django.core.management.color import color_style
from django.utils.translation import gettext_lazy as _
from wagtail.models import Collection, Page, PageViewRestriction, Site

from sites_conformes.core.constants import HEADER_FIELDS
from sites_conformes.core.models import CatalogIndexPage
from sites_conformes.core.utils import get_default_site
from sites_conformes.menus.models import FooterBottomMenu, MainMenu

ContentPage = swapper.load_model("sites_conformes_core", "ContentPage")
style = color_style()


def get_existing_pages(page_model, root_page: Page, parent_page: Page):
    """
    Pages of the given model where an existing page is looked up: below the root page of the site,
    and below the parent page when it is outside the site (such as the page templates index,
    created right under the root of the tree).
    """
    pages = page_model.objects.descendant_of(root_page, inclusive=True)
    if not parent_page.path.startswith(root_page.path):
        pages = pages | page_model.objects.descendant_of(parent_page, inclusive=True)
    return pages


def get_or_create_collection(col_name: str) -> Collection:
    """
    Get the collection with the given name, or create it right under the root collection.
    """
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
    site: Site | None = None,
) -> CatalogIndexPage:
    """
    Get a CatalogIndexPage if it exists, or creates it instead.

    Pages are looked up by slug in the locale of the site, anywhere below its root page
    (or below the parent page, when it is outside the site):
    an existing page is returned as is, without being updated.

    - `body`: the StreamField value, as a list of `(block_name, value)` tuples.
    - `parent_page`: defaults to the root page of the site.
    - `restriction_type`: if set, a `PageViewRestriction` of this type
      (such as "login") is added to the new page.
    - `page_fields`: other fields to set on the new page; only the header fields
      (`HEADER_FIELDS`) and `source_url` are taken into account.
    - `site`: defaults to the default site.
    """

    site = site or get_default_site()
    root_page = site.root_page
    locale = root_page.locale

    if parent_page:
        if not isinstance(parent_page, (Page, ContentPage)):
            # Default "Page" type is allowed to allow the default root page"
            raise TypeError("The parent page should be a content page.")
    else:
        # If parent_page is not passed as parameter, use the Home page of the site.
        if not isinstance(root_page, (Page, ContentPage)):
            raise TypeError("The parent page should be a content page.")
        parent_page = root_page

    # Don't replace or duplicate an already existing page
    already_exists = (
        get_existing_pages(CatalogIndexPage, root_page, parent_page).filter(slug=slug, locale=locale).first()
    )
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
    site: Site | None = None,
) -> ContentPage:
    """
    Get a ContentPage if it exists, or creates it instead.

    Pages are looked up by slug in the locale of the site, anywhere below its root page
    (or below the parent page, when it is outside the site):
    an existing page is returned as is, without being updated.

    - `body`: the StreamField value, as a list of `(block_name, value)` tuples.
    - `parent_page`: defaults to the root page of the site.
    - `restriction_type`: if set, a `PageViewRestriction` of this type
      (such as "login") is added to the new page.
    - `page_fields`: other fields to set on the new page; only the header fields
      (`HEADER_FIELDS`) and `source_url` are taken into account.
    - `site`: defaults to the default site.
    """

    site = site or get_default_site()
    root_page = site.root_page
    locale = root_page.locale

    if parent_page:
        if not isinstance(parent_page, (Page, ContentPage, CatalogIndexPage)):
            # Default "Page" type is allowed to allow the default root page"
            raise TypeError("The parent page should be a content page or a catalog index page.")
    else:
        # If parent_page is not passed as parameter, use the Home page of the site.
        if not isinstance(root_page, (Page, ContentPage, CatalogIndexPage)):
            raise TypeError("The parent page should be a content page or a catalog index page.")
        parent_page = root_page

    # Don't replace or duplicate an already existing page
    already_exists = get_existing_pages(ContentPage, root_page, parent_page).filter(slug=slug, locale=locale).first()
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


def get_or_create_footer_bottom_menu(site: Site | None = None) -> FooterBottomMenu:
    """
    Get the footer menu of the site (in the locale of its root page), or create it if it doesn't already exist.
    The site defaults to the default site.

    In any case, return it.
    """

    site = site or get_default_site()
    locale = site.root_page.locale

    footer_menu, _created = FooterBottomMenu.objects.get_or_create(site=site, locale=locale)

    return footer_menu


def get_or_create_main_menu(site: Site | None = None) -> MainMenu:
    """
    Get the main menu of the site (in the locale of its root page), or create it if it doesn't already exist.
    The site defaults to the default site.

    In any case, return it.
    A new main menu gets a link to the home page.
    """

    site = site or get_default_site()
    root_page = site.root_page
    locale = root_page.locale

    main_menu, created = MainMenu.objects.get_or_create(site=site, locale=locale)

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
