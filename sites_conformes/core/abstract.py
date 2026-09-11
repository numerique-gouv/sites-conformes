from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from dsfr.constants import COLOR_CHOICES
from rest_framework import serializers
from taggit.models import Tag as TaggitTag
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, TitleFieldPanel
from wagtail.admin.widgets.slug import SlugInput
from wagtail.api import APIField
from wagtail.contrib.routable_page.models import RoutablePageMixin
from wagtail.fields import RichTextField, StreamField
from wagtail.images import get_image_model_string
from wagtail.images.api.fields import ImageRenditionField
from wagtail.models import Orderable, Page
from wagtail.models.i18n import TranslatableMixin
from wagtail.search import index
from wagtail.snippets.models import register_snippet

from sites_conformes.core.blocks.buttons_links import ButtonsHorizontalListBlock
from sites_conformes.core.blocks.colophon import COLOPHON_BLOCKS
from sites_conformes.core.blocks.core import HERO_STREAMFIELD_BLOCKS, STREAMFIELD_COMMON_BLOCKS
from sites_conformes.core.constants import LIMITED_RICHTEXTFIELD_FEATURES
from sites_conformes.core.managers import TagManager
from sites_conformes.core.utils import get_streamfield_raw_text


class SitesFacilesBasePage(Page):
    """
    This class defines a base page model that will be used
    by all pages in the site.
    """

    hero = StreamField(HERO_STREAMFIELD_BLOCKS, blank=True, use_json_field=True, max_num=1)

    body = StreamField(
        STREAMFIELD_COMMON_BLOCKS,
        blank=True,
        use_json_field=True,
        collapsed=True,
    )
    header_with_title = models.BooleanField(_("Show title in header image?"), default=False)  # type: ignore

    header_image = models.ForeignKey(
        get_image_model_string(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("Header image"),
    )

    header_color_class = models.CharField(
        _("Background color"),
        choices=COLOR_CHOICES,
        null=True,
        blank=True,
        help_text=_("Uses the French Design System colors"),
    )

    header_large = models.BooleanField(_("Full width"), default=False)  # type: ignore
    header_darken = models.BooleanField(_("Darken background image"), default=False)  # type: ignore

    header_cta_text = RichTextField(
        _("Call to action text"),
        null=True,
        blank=True,
    )

    header_cta_buttons = StreamField(
        [
            (
                "buttons",
                ButtonsHorizontalListBlock(
                    help_text=_("""Please use only one primary button.
                        If you use icons, use them on all buttons and align them on the same side."""),
                    label=_("Buttons"),
                ),
            ),
        ],
        max_num=1,
        null=True,
        blank=True,
    )

    source_url = models.URLField(
        _("Source URL"),
        help_text=_("For imported pages, to allow updates. Max length: 2000 characters."),
        max_length=2000,
        null=True,
        blank=True,
    )

    exclude_from_sitemap = models.BooleanField(
        _("Exclude from sitemap"),
        default=False,
        help_text=_(
            "If checked, this page will be excluded from sitemap.xml,"
            " the plan du site page, and will have a noindex meta tag."
        ),
    )

    preview_image = models.ForeignKey(
        get_image_model_string(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("Preview image"),
        help_text=_("Image displayed as a preview when the page is shared on social media"),
    )

    content_panels = Page.content_panels + [
        FieldPanel(
            "hero",
            heading=_("Hero"),
            help_text=_(
                "Header section of the page. If empty, no header is displayed "
                "and the page title appears at the top of the content."
            ),
        ),
        FieldPanel("body", heading=_("Body")),
    ]

    promote_panels = [
        MultiFieldPanel(
            [
                "slug",
                "seo_title",
                "search_description",
                "exclude_from_sitemap",
            ],
            _("For search engines"),
        ),
        FieldPanel("preview_image"),
    ]

    search_fields = Page.search_fields + [
        index.SearchField("body"),
    ]

    # Export fields over the API
    api_fields = [
        APIField("hero"),
        APIField("body"),
        APIField("header_image"),
        APIField("header_image_render", serializer=ImageRenditionField("fill-1200x630", source="header_image")),
        APIField("header_image_thumbnail", serializer=ImageRenditionField("fill-376x211", source="header_image")),
        APIField("header_with_title"),
        APIField("header_color_class"),
        APIField("header_large"),
        APIField("header_darken"),
        APIField("header_cta_text"),
        APIField("header_cta_buttons"),
        APIField("public_child_pages"),
        APIField("preview_image"),
        APIField("preview_image_render", serializer=ImageRenditionField("fill-1200x630", source="preview_image")),
    ]

    @property
    def public_child_pages(self):
        return [
            {
                "id": child.id,
                "slug": child.slug,
                "title": child.title,
                "type": f"{child.content_type.app_label}.{child.content_type.model}",
            }
            for child in self.get_children().live().public()
        ]

    @property
    def get_preview_image(self):
        return self.preview_image or self.header_image

    @property
    def show_title(self):
        for block in self.hero:
            if block.block_type != "old_hero":
                return False

            if block.value.get("header_with_title") is True:
                return False
        return True

    @property
    def cover(self):
        hero_blocks = getattr(self, "hero", None)

        if not hero_blocks:
            return None

        first_hero = hero_blocks[0].value or {}

        if "image" in first_hero:
            image_block = first_hero.get("image")
            if isinstance(image_block, dict) and "image" in image_block:
                return image_block.get("image")
            return image_block

        if "header_image" in first_hero:
            return first_hero.get("header_image")

        return None

    def get_sitemap_urls(self, request=None):
        if self.exclude_from_sitemap:
            return []
        return super().get_sitemap_urls(request)

    def get_absolute_url(self):
        return self.url

    def save(self, *args, **kwargs):
        if not self.search_description:
            search_description = get_streamfield_raw_text(self.body, max_words=20)
            if search_description:
                self.search_description = search_description
        return super().save(*args, **kwargs)

    exclude_fields_in_copy = ["source_url"]

    class Meta:
        abstract = True
        verbose_name = _("Base page")
        verbose_name_plural = _("Base pages")


@register_snippet
class Category(TranslatableMixin, index.Indexed, Orderable):
    name = models.CharField(max_length=80, unique=True, verbose_name=_("Category name"))
    slug = models.SlugField(unique=True, max_length=80)
    parent = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        related_name="children",
        verbose_name=_("Parent category"),
        on_delete=models.SET_NULL,
    )
    description = RichTextField(
        max_length=500,
        features=LIMITED_RICHTEXTFIELD_FEATURES,
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Displayed on the top of the category page"),
    )  # type: ignore
    colophon = StreamField(
        COLOPHON_BLOCKS,
        blank=True,
        use_json_field=True,
        help_text=_("Text displayed at the end of every page in the category"),
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

    search_fields = [index.SearchField("name")]

    class Meta:
        ordering = ["name"]
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        unique_together = [
            ("translation_key", "locale"),
            ("name", "locale"),
            ("slug", "locale"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.parent:
            parent = self.parent
            if self.parent == self:
                raise ValidationError(_("Parent category cannot be self."))
            if parent.parent and parent.parent == self:
                raise ValidationError(_("Cannot have circular Parents."))

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description", "colophon", "parent")
        depth = 1


@register_snippet
class Tag(TaggitTag):
    objects = TagManager()

    class Meta:
        proxy = True
        verbose_name = _("Tag")


class AbstractIndexPage(RoutablePageMixin, SitesFacilesBasePage):
    posts_per_page = models.PositiveSmallIntegerField(
        default=10,
        validators=[MaxValueValidator(100), MinValueValidator(1)],
        verbose_name=_("Entries per page"),
    )
    filter_by_tag = models.BooleanField(_("Filter by tag"), default=True)
    filter_by_category = models.BooleanField(_("Filter by category"), default=True)

    tagged_title = _("Pages tagged with %(tag)s")
    in_category_title = _("Pages in category %(category)s")
    tags_route = None
    categories_route = None

    class Meta:
        abstract = True

    @property
    def posts(self) -> models.QuerySet:
        raise NotImplementedError

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        posts, filters = self.apply_filters(request, self.posts)
        paginator = Paginator(posts, self.posts_per_page)
        context.update(filters)
        context.update(
            posts=paginator.get_page(request.GET.get("page")),
            paginator=paginator,
            tags=self.get_tags(),
            categories=self.get_categories(),
        )
        return context

    def apply_filters(self, request: HttpRequest, posts: models.QuerySet) -> tuple[models.QuerySet, dict]:
        context = {"current_tag": None, "current_category": None, "extra_title": "", "extra_breadcrumbs": None}
        posts = self.apply_tag_filter(request, posts, context)
        posts = self.apply_category_filter(request, posts, context)
        return posts, context

    def apply_tag_filter(self, request: HttpRequest, posts: models.QuerySet, context: dict) -> models.QuerySet:
        slug = request.GET.get("tag")
        if not slug:
            return posts
        tag = get_object_or_404(Tag, slug=slug)
        context.update(
            current_tag=tag,
            extra_title=self.tagged_title % {"tag": tag},
            extra_breadcrumbs=self.filter_breadcrumbs(tag, self.tags_route, _("Tags")),
        )
        return posts.filter(tags=tag)

    def apply_category_filter(self, request: HttpRequest, posts: models.QuerySet, context: dict) -> models.QuerySet:
        slug = request.GET.get("category")
        if not slug:
            return posts
        category = get_object_or_404(Category, slug=slug, locale=self.locale)
        context.update(
            current_category=category,
            extra_title=self.in_category_title % {"category": category.name},
            extra_breadcrumbs=self.filter_breadcrumbs(category.name, self.categories_route, _("Categories")),
        )
        return posts.filter(categories=category)

    def filter_breadcrumbs(self, current, route_name: str | None = None, route_title: str = "") -> dict:
        links = [{"url": self.get_url(), "title": self.title}]
        if route_name:
            links.append({"url": f"{self.get_url()}{self.reverse_subpage(route_name)}", "title": route_title})
        return {"links": links, "current": current}

    def get_tags(self) -> models.QuerySet:
        ids = self.posts.specific().values_list("tags", flat=True)
        return Tag.objects.filter(id__in=ids).order_by("name")

    def get_categories(self) -> models.QuerySet:
        ids = self.posts.specific().values_list("categories", flat=True)
        return Category.objects.filter(id__in=ids).order_by("name")
