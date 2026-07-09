"""Search result filters (fork-specific; mirrors PublicationIndexPage and blog facets)."""

from dataclasses import dataclass

from django.shortcuts import get_object_or_404

from publications.models import Collection, PublicationPage, Theme
from sites_conformes.blog.models import BlogEntryPage, Category, Organization, Person
from sites_conformes.core.models import ContentPage, Tag


def get_enabled_filters() -> dict[str, bool]:
    """Which filter sections to show on the search page."""
    return {
        "filter_by_category": True,
        "filter_by_collection": True,
        "filter_by_theme": True,
        "filter_by_tag": True,
        "filter_by_author": True,
        "filter_by_source": True,
        "filter_by_year": True,
    }


@dataclass
class ActiveFilters:
    category: Category | None = None
    collection: Collection | None = None
    theme: Theme | None = None
    tag: Tag | None = None
    source: Organization | None = None
    author: Person | None = None
    year: str | None = None


def resolve_active_filters(request, site) -> ActiveFilters:
    """Resolve active filter objects from GET parameters."""
    locale = site.root_page.localized.locale
    active = ActiveFilters()

    category_slug = request.GET.get("category")
    if category_slug:
        active.category = get_object_or_404(Category, slug=category_slug, locale=locale)

    collection_slug = request.GET.get("collection")
    if collection_slug:
        active.collection = get_object_or_404(Collection, slug=collection_slug, locale=locale)

    theme_slug = request.GET.get("theme")
    if theme_slug:
        active.theme = get_object_or_404(Theme, slug=theme_slug, locale=locale)

    tag_slug = request.GET.get("tag")
    if tag_slug:
        active.tag = get_object_or_404(Tag, slug=tag_slug)

    source_slug = request.GET.get("source")
    if source_slug:
        active.source = get_object_or_404(Organization, slug=source_slug)

    author_id = request.GET.get("author")
    if author_id:
        active.author = get_object_or_404(Person, id=author_id)

    active.year = request.GET.get("year") or None
    return active


def filter_queryset(request, queryset, site):
    """Apply GET filter params before full-text search (see ``filter_before_search``)."""
    root = site.root_page.localized
    active = resolve_active_filters(request, site)
    page_ids: set[int] | None = None

    def intersect_page_ids(ids):
        nonlocal page_ids
        ids = set(ids)
        page_ids = ids if page_ids is None else page_ids & ids

    if active.category:
        intersect_page_ids(
            BlogEntryPage.objects.descendant_of(root)
            .live()
            .filter(blog_categories=active.category)
            .values_list("pk", flat=True)
        )

    if active.collection:
        intersect_page_ids(
            PublicationPage.objects.descendant_of(root)
            .live()
            .filter(collections=active.collection)
            .values_list("pk", flat=True)
        )

    if active.theme:
        intersect_page_ids(
            PublicationPage.objects.descendant_of(root).live().filter(themes=active.theme).values_list("pk", flat=True)
        )

    if active.tag:
        tag_page_ids = set(
            ContentPage.objects.descendant_of(root).live().filter(tags=active.tag).values_list("pk", flat=True)
        )
        tag_page_ids |= set(
            BlogEntryPage.objects.descendant_of(root).live().filter(tags=active.tag).values_list("pk", flat=True)
        )
        intersect_page_ids(tag_page_ids)

    if active.source:
        intersect_page_ids(
            BlogEntryPage.objects.descendant_of(root)
            .live()
            .filter(authors__organization=active.source)
            .values_list("pk", flat=True)
        )

    if active.author:
        intersect_page_ids(
            BlogEntryPage.objects.descendant_of(root).live().filter(authors=active.author).values_list("pk", flat=True)
        )

    if active.year:
        intersect_page_ids(
            BlogEntryPage.objects.descendant_of(root)
            .live()
            .filter(date__year=active.year)
            .values_list("pk", flat=True)
        )

    if page_ids is not None:
        queryset = queryset.filter(pk__in=page_ids)

    return queryset


def get_filter_context(request, site) -> dict:
    """Build context for the filter sidebar: enabled filters, filter values lists, active filter values."""
    root = site.root_page.localized
    locale = root.locale
    blog_entries = BlogEntryPage.objects.descendant_of(root).live()
    content_pages = ContentPage.objects.descendant_of(root).live()
    publication_pages = PublicationPage.objects.descendant_of(root).live()
    active = resolve_active_filters(request, site)

    context = {
        **get_enabled_filters(),
        "current_category": active.category,
        "current_collection": active.collection,
        "current_theme": active.theme,
        "current_tag": active.tag,
        "current_source": active.source,
        "current_author": active.author,
        "year": active.year,
    }

    if context["filter_by_category"]:
        category_ids = blog_entries.values_list("blog_categories", flat=True)
        context["categories"] = Category.objects.filter(id__in=category_ids, locale=locale).order_by("name")

    if context["filter_by_tag"]:
        tag_ids = set(content_pages.values_list("tags", flat=True))
        tag_ids |= set(blog_entries.values_list("tags", flat=True))
        tag_ids.discard(None)
        context["tags"] = Tag.objects.filter(id__in=tag_ids).order_by("name")

    if context["filter_by_author"]:
        author_ids = blog_entries.values_list("authors", flat=True)
        context["authors"] = Person.objects.filter(id__in=author_ids).order_by("name")

    if context["filter_by_source"]:
        org_ids = blog_entries.values_list("authors__organization", flat=True)
        context["sources"] = Organization.objects.filter(id__in=org_ids).order_by("name")

    if context["filter_by_collection"]:
        collection_ids = publication_pages.values_list("collections", flat=True)
        context["collections"] = Collection.objects.filter(id__in=collection_ids, locale=locale).order_by("name")

    if context["filter_by_theme"]:
        theme_ids = publication_pages.values_list("themes", flat=True)
        context["themes"] = Theme.objects.filter(id__in=theme_ids, locale=locale).order_by("name")

    context["show_search_filters"] = _show_search_filters(context)
    return context


def _show_search_filters(context: dict) -> bool:
    if context.get("filter_by_category") and context.get("categories"):
        return True
    if context.get("filter_by_collection") and context.get("collections"):
        return True
    if context.get("filter_by_theme") and context.get("themes"):
        return True
    if context.get("filter_by_tag") and context.get("tags"):
        return True
    if context.get("filter_by_author") and context.get("authors"):
        return True
    if context.get("filter_by_source") and context.get("sources"):
        return True
    return False
