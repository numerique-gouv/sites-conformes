from django.db.models import Count
from django.db.models.expressions import F

_taxonomies = {}


class Taxonomy:
    """Configuration for one taxonomy on an entry page type (e.g. blog categories)."""

    def __init__(
        self,
        slug,
        model,
        m2m_field,
        filter_field,
        filter_heading,
        list_label_plural,
        list_route_name,
        list_template,
        list_prefix,
        list_context_key,
        current_context_key,
        filtered_title,
        filtered_title_param,
    ):
        self.slug = slug
        self.model = model
        self.m2m_field = m2m_field
        self.filter_field = filter_field
        self.filter_heading = filter_heading
        self.list_label_plural = list_label_plural
        self.list_route_name = list_route_name
        self.list_template = list_template
        self.list_prefix = list_prefix
        self.list_context_key = list_context_key
        self.current_context_key = current_context_key
        self.filtered_title = filtered_title
        self.filtered_title_param = filtered_title_param

    @property
    def list_slug_path(self):
        return f"{self.m2m_field}__slug"

    @property
    def list_name_path(self):
        return f"{self.m2m_field}__name"


def register_taxonomies(entry_page_class, taxonomies):
    """Associate taxonomy definitions with an entry page class.

    Example: ``register_taxonomies(BlogEntryPage, [CATEGORY])`` in ``BlogConfig.ready()``.
    """
    _taxonomies[entry_page_class] = taxonomies


def get_taxonomy_types(entry_page_class):
    """Return taxonomy *definitions* registered for an entry page class.

    This is metadata (slug, model, template, …), not database rows.

    Example::

        get_taxonomy_types(BlogEntryPage)
        # → [CATEGORY]   # the Taxonomy object from taxonomies.py

        get_taxonomy_types(PublicationPage)
        # → [COLLECTION, THEME]

    ``BlogIndexPage.get_context`` loops over this list to know which filters
    to apply and which context keys to fill (``categories``, ``collections``, …).
    """
    return _taxonomies.get(entry_page_class, [])


def get_taxonomy_values(index_page, taxonomy):
    """Return taxonomy *instances* present on posts under an index page.

    This is the data shown in filter sidebars — the same as the old
    ``BlogIndexPage.get_categories()`` method.

    Example::

        get_taxonomy_values(my_blog_index_page, CATEGORY)
        # → <QuerySet [<Category: Agriculture>, <Category: Climate>]>

    Only categories linked to at least one live post under ``index_page`` are
    returned, ordered by name.
    """
    ids = index_page.posts.specific().values_list(
        taxonomy.m2m_field,
        flat=True,
    )
    return taxonomy.model.objects.filter(id__in=ids).order_by("name")


def list_taxonomy_values(index_page, taxonomy):
    """Return taxonomy values with post counts, for a taxonomy list page.

    Example::

        list_taxonomy_values(my_blog_index_page, CATEGORY)
        # → [
        #     {"cat_slug": "agriculture", "cat_name": "Agriculture", "cat_count": 12},
        #     {"cat_slug": "climate", "cat_name": "Climate", "cat_count": 3},
        #   ]

    Used by ``BlogIndexPage.categories_list`` (via ``render_taxonomy_list``).
    """
    posts = index_page.posts.specific()
    slug_key = f"{taxonomy.list_prefix}_slug"
    name_key = f"{taxonomy.list_prefix}_name"
    count_key = f"{taxonomy.list_prefix}_count"
    return (
        posts.values(
            **{
                slug_key: F(taxonomy.list_slug_path),
                name_key: F(taxonomy.list_name_path),
            },
        )
        .annotate(**{count_key: Count(slug_key)})
        .filter(**{f"{count_key}__gte": 1})
        .order_by(f"-{count_key}")
    )
