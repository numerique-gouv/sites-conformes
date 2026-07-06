from django.db import models
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.api import APIField
from wagtail.contrib.routable_page.models import path
from wagtail.models import Orderable

from publications.taxonomy import AbstractTaxonomy
from sites_conformes.blog.models import BlogEntryPage, BlogIndexPage


class Collection(AbstractTaxonomy):
    class Meta(AbstractTaxonomy.Meta):
        verbose_name = _("Collection")
        verbose_name_plural = _("Collections")


class Theme(AbstractTaxonomy):
    class Meta(AbstractTaxonomy.Meta):
        verbose_name = _("Theme")
        verbose_name_plural = _("Themes")


class CollectionPublication(Orderable):
    """Through table linking collections to publication pages."""

    collection = models.ForeignKey(
        Collection, related_name="+", verbose_name=_("Collection"), on_delete=models.CASCADE
    )
    page = ParentalKey("PublicationPage", related_name="entry_collections")  # type: ignore
    panels = [FieldPanel("collection")]

    def __str__(self):
        return str(self.collection)


class ThemePublication(Orderable):
    """Through table linking themes to publication pages."""

    theme = models.ForeignKey(Theme, related_name="+", verbose_name=_("Theme"), on_delete=models.CASCADE)
    page = ParentalKey("PublicationPage", related_name="entry_themes")  # type: ignore
    panels = [FieldPanel("theme")]

    def __str__(self):
        return str(self.theme)


class PublicationPage(BlogEntryPage):
    collections = ParentalManyToManyField(
        "Collection",
        through="CollectionPublication",
        blank=True,
        verbose_name=_("Collections"),
    )
    themes = ParentalManyToManyField(
        "Theme",
        through="ThemePublication",
        blank=True,
        verbose_name=_("Themes"),
    )

    parent_page_types = ["publications.PublicationIndexPage"]
    subpage_types = []
    template = "publications/publication_page.html"

    settings_panels = BlogEntryPage.settings_panels[:]
    _tags_panel_index = next(
        i for i, panel in enumerate(settings_panels) if getattr(panel, "heading", None) == _("Tags and Categories")
    )
    settings_panels[_tags_panel_index] = MultiFieldPanel(
        [
            FieldPanel("collections"),
            FieldPanel("themes"),
            FieldPanel("tags"),
        ],
        heading=_("Tags, collections and themes"),
    )

    api_fields = [
        # Exclude blog_categories from the API fields
        field
        for field in BlogEntryPage.api_fields
        if field.name not in ("blog_categories",)
    ] + [
        APIField("collections"),
        APIField("themes"),
    ]

    class Meta:
        verbose_name = _("Publication page")


class PublicationIndexPage(BlogIndexPage):
    filter_by_collection = models.BooleanField(_("Filter by collection"), default=True)
    filter_by_theme = models.BooleanField(_("Filter by theme"), default=True)

    settings_panels = BlogIndexPage.settings_panels[:]
    _filters_panel_index = next(
        i for i, panel in enumerate(settings_panels) if getattr(panel, "heading", None) == _("Show filters")
    )
    settings_panels[_filters_panel_index] = MultiFieldPanel(
        [
            FieldPanel("filter_by_collection"),
            FieldPanel("filter_by_theme"),
            FieldPanel("filter_by_tag"),
            FieldPanel("filter_by_author"),
            FieldPanel("filter_by_source"),
        ],
        heading=_("Show filters"),
    )

    subpage_types = ["publications.PublicationPage"]
    template = "publications/publication_index_page.html"

    class Meta:
        verbose_name = _("Publication index")

    def get_collections(self):
        from publications.taxonomies import COLLECTION
        from sites_conformes.blog.taxonomy import get_taxonomy_values

        return get_taxonomy_values(self, COLLECTION)

    def get_themes(self):
        from publications.taxonomies import THEME
        from sites_conformes.blog.taxonomy import get_taxonomy_values

        return get_taxonomy_values(self, THEME)

    @path("collections/", name="collections_list")
    def collections_list(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        from publications.taxonomies import COLLECTION

        return self.render_taxonomy_list(request, COLLECTION)

    @path("themes/", name="themes_list")
    def themes_list(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        from publications.taxonomies import THEME

        return self.render_taxonomy_list(request, THEME)
