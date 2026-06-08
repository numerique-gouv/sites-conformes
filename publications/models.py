from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import models
from django.db.models import BooleanField, Count, QuerySet
from django.db.models.expressions import F
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import slugify
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from wagtail.admin.panels import FieldPanel, FieldRowPanel, MultiFieldPanel, TitleFieldPanel
from wagtail.admin.widgets.slug import SlugInput
from wagtail.api import APIField
from wagtail.contrib.routable_page.models import path
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Orderable
from wagtail.models.i18n import TranslatableMixin
from wagtail.search import index

from sites_conformes.blog.blocks import COLOPHON_BLOCKS
from sites_conformes.blog.models import BlogEntryPage, BlogIndexPage, Person
from sites_conformes.core.constants import LIMITED_RICHTEXTFIELD_FEATURES
from sites_conformes.core.models import Tag


class Collection(TranslatableMixin, index.Indexed, Orderable):
    name = models.CharField(max_length=80, unique=True, verbose_name=_("Collection name"))
    slug = models.SlugField(unique=True, max_length=80)
    parent = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        related_name="children",
        verbose_name=_("Parent collection"),
        on_delete=models.SET_NULL,
    )
    description = RichTextField(
        max_length=500,
        features=LIMITED_RICHTEXTFIELD_FEATURES,
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Displayed on the top of the collection page"),
    )  # type: ignore
    colophon = StreamField(
        COLOPHON_BLOCKS,
        blank=True,
        use_json_field=True,
        help_text=_("Text displayed at the end of every page in the collection"),
    )
    panels = [
        TitleFieldPanel("name"),
        FieldPanel("slug", widget=SlugInput),
        FieldPanel("description"),
        FieldPanel("colophon"),
        FieldPanel("parent"),
    ]

    api_fields = [
        APIField("name"),
        APIField("slug"),
        APIField("description"),
        APIField("colophon"),
        APIField("parent"),
    ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.parent:
            parent = self.parent
            if self.parent == self:
                raise ValidationError(_("Parent collection cannot be self."))
            if parent.parent and parent.parent == self:
                raise ValidationError(_("Cannot have circular Parents."))

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)

    class Meta:
        ordering = ["name"]
        verbose_name = _("Collection")
        verbose_name_plural = _("Collections")
        unique_together = [
            ("translation_key", "locale"),
            ("name", "locale"),
            ("slug", "locale"),
        ]

    search_fields = [index.SearchField("name")]


class Theme(TranslatableMixin, index.Indexed, Orderable):
    name = models.CharField(max_length=80, unique=True, verbose_name=_("Theme name"))
    slug = models.SlugField(unique=True, max_length=80)
    parent = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        related_name="children",
        verbose_name=_("Parent theme"),
        on_delete=models.SET_NULL,
    )
    description = RichTextField(
        max_length=500,
        features=LIMITED_RICHTEXTFIELD_FEATURES,
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Displayed on the top of the theme page"),
    )  # type: ignore
    colophon = StreamField(
        COLOPHON_BLOCKS,
        blank=True,
        use_json_field=True,
        help_text=_("Text displayed at the end of every page in the theme"),
    )
    panels = [
        TitleFieldPanel("name"),
        FieldPanel("slug", widget=SlugInput),
        FieldPanel("description"),
        FieldPanel("colophon"),
        FieldPanel("parent"),
    ]

    api_fields = [
        APIField("name"),
        APIField("slug"),
        APIField("description"),
        APIField("colophon"),
        APIField("parent"),
    ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.parent:
            parent = self.parent
            if self.parent == self:
                raise ValidationError(_("Parent theme cannot be self."))
            if parent.parent and parent.parent == self:
                raise ValidationError(_("Cannot have circular Parents."))

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)

    class Meta:
        ordering = ["name"]
        verbose_name = _("Theme")
        verbose_name_plural = _("Themes")
        unique_together = [
            ("translation_key", "locale"),
            ("name", "locale"),
            ("slug", "locale"),
        ]

    search_fields = [index.SearchField("name")]


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
        i
        for i, panel in enumerate(settings_panels)
        if getattr(panel, "heading", None) == _("Tags and Categories")
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
        i
        for i, panel in enumerate(settings_panels)
        if getattr(panel, "heading", None) == _("Show filters")
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

    @property
    def posts(self):
        posts = PublicationPage.objects.descendant_of(self).live()
        posts = (
            posts.order_by("-date")
            .select_related("owner")
            .prefetch_related("tags", "collections", "themes", "date__year")
        )
        return posts

    def get_context(self, request, *args, **kwargs):
        context = super(BlogIndexPage, self).get_context(request, *args, **kwargs)
        posts = self.posts

        extra_breadcrumbs = None
        extra_title = ""

        tag = None
        collection = None
        theme = None
        source = None
        author = None

        tag_slug = request.GET.get("tag")
        if tag_slug:
            tag = get_object_or_404(Tag, slug=tag_slug)
            posts = posts.filter(tags=tag)
            extra_breadcrumbs = {
                "links": [
                    {"url": self.get_url(), "title": self.title},
                    {
                        "url": f"{self.get_url()}{self.reverse_subpage('tags_list')}",
                        "title": _("Tags"),
                    },
                ],
                "current": tag,
            }
            extra_title = _("Posts tagged with %(tag)s") % {"tag": tag}

        collection_slug = request.GET.get("collection")
        if collection_slug:
            collection = get_object_or_404(Collection, slug=collection_slug, locale=self.locale)
            posts = posts.filter(collections=collection)
            extra_breadcrumbs = {
                "links": [
                    {"url": self.get_url(), "title": self.title},
                    {
                        "url": f"{self.get_url()}{self.reverse_subpage('collections_list')}",
                        "title": _("Collections"),
                    },
                ],
                "current": collection.name,
            }
            extra_title = _("Posts in collection %(collection)s") % {"collection": collection.name}

        theme_slug = request.GET.get("theme")
        if theme_slug:
            theme = get_object_or_404(Theme, slug=theme_slug, locale=self.locale)
            posts = posts.filter(themes=theme)
            extra_breadcrumbs = {
                "links": [
                    {"url": self.get_url(), "title": self.title},
                    {
                        "url": f"{self.get_url()}{self.reverse_subpage('themes_list')}",
                        "title": _("Themes"),
                    },
                ],
                "current": theme.name,
            }
            extra_title = _("Posts in theme %(theme)s") % {"theme": theme.name}

        source_slug = request.GET.get("source")
        if source_slug:
            from sites_conformes.blog.models import Organization

            source = get_object_or_404(Organization, slug=source_slug)
            posts = posts.filter(authors__organization=source)
            extra_breadcrumbs = {
                "links": [
                    {"url": self.get_url(), "title": self.title},
                ],
                "current": _("Posts written by") + f" {source.name}",
            }
            extra_title = _("Posts written by") + f" {source.name}"

        author_id = request.GET.get("author")
        if author_id:
            author = get_object_or_404(Person, id=author_id)
            extra_breadcrumbs = {
                "links": [
                    {"url": self.get_url(), "title": self.title},
                ],
                "current": _("Posts written by") + f" {author.name}",
            }
            posts = posts.filter(authors=author)
            extra_title = _("Posts written by") + f" {author.name}"

        year = request.GET.get("year")
        if year:
            posts = posts.filter(date__year=year)
            extra_title = _("Posts published in %(year)s") % {"year": year}

        page_number = request.GET.get("page")
        paginator = Paginator(posts, self.posts_per_page)
        posts = paginator.get_page(page_number)

        context["posts"] = posts
        context["current_collection"] = collection
        context["current_theme"] = theme
        context["current_tag"] = tag
        context["current_source"] = source
        context["current_author"] = author
        context["year"] = year
        context["paginator"] = paginator
        context["extra_title"] = extra_title

        context["collections"] = self.get_collections()
        context["themes"] = self.get_themes()
        context["authors"] = self.get_authors()
        context["sources"] = self.get_sources()
        context["tags"] = self.get_tags()

        if extra_breadcrumbs:
            context["extra_breadcrumbs"] = extra_breadcrumbs

        return context

    def get_collections(self) -> QuerySet:
        ids = self.posts.specific().values_list("collections", flat=True)
        return Collection.objects.filter(id__in=ids).order_by("name")

    def get_themes(self) -> QuerySet:
        ids = self.posts.specific().values_list("themes", flat=True)
        return Theme.objects.filter(id__in=ids).order_by("name")

    def list_collections(self) -> list:
        posts = self.posts.specific()
        return (
            posts.values(
                coll_slug=F("collections__slug"),
                coll_name=F("collections__name"),
            )
            .annotate(coll_count=Count("coll_slug"))
            .filter(coll_count__gte=1)
            .order_by("-coll_count")
        )

    def list_themes(self) -> list:
        posts = self.posts.specific()
        return (
            posts.values(
                theme_slug=F("themes__slug"),
                theme_name=F("themes__name"),
            )
            .annotate(theme_count=Count("theme_slug"))
            .filter(theme_count__gte=1)
            .order_by("-theme_count")
        )

    @property
    def show_filters(self) -> bool | BooleanField:
        return (
            self.filter_by_collection
            or self.filter_by_theme
            or self.filter_by_tag
            or self.filter_by_author
            or self.filter_by_source
        )

    def feed_posts(self, feed, request):
        posts = self.posts

        collection = request.GET.get("collection")
        if collection:
            collection = get_object_or_404(Collection, slug=collection, locale=self.locale)
            posts = posts.filter(collections=collection)

        theme = request.GET.get("theme")
        if theme:
            theme = get_object_or_404(Theme, slug=theme, locale=self.locale)
            posts = posts.filter(themes=theme)

        limit = int(request.GET.get("limit", self.feed_posts_limit))
        posts = posts[:limit]

        for post in posts:
            feed.add_item(
                post.title,
                post.full_url,
                pubdate=post.date,
                description=post.search_description,
            )

        return feed

    @path("collections/", name="collections_list")
    def collections_list(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        extra_title = _("Collections")
        collections = self.list_collections()

        extra_breadcrumbs = {
            "links": [
                {"url": self.get_url(), "title": self.title},
            ],
            "current": _("Collections"),
        }

        return self.render(
            request,
            context_overrides={
                "collections": collections,
                "page": self,
                "extra_title": extra_title,
                "extra_breadcrumbs": extra_breadcrumbs,
            },
            template="publications/collections_list_page.html",
        )

    @path("themes/", name="themes_list")
    def themes_list(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        extra_title = _("Themes")
        themes = self.list_themes()

        extra_breadcrumbs = {
            "links": [
                {"url": self.get_url(), "title": self.title},
            ],
            "current": _("Themes"),
        }

        return self.render(
            request,
            context_overrides={
                "themes": themes,
                "page": self,
                "extra_title": extra_title,
                "extra_breadcrumbs": extra_breadcrumbs,
            },
            template="publications/themes_list_page.html",
        )
