from django.apps import apps
from django.core.paginator import Paginator
from django.db import models
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _

from sites_conformes.core.abstract import AbstractIndexPage


class AbstractAuthoredIndexPage(AbstractIndexPage):
    """
    Index page whose entries have categories and authors: blog posts and events.

    Subclasses set the ``*_title`` attributes to their own wording. They stay
    literal ``gettext_lazy`` calls so gettext keeps extracting them.
    """

    filter_by_category = models.BooleanField(_("Filter by category"), default=True)
    filter_by_tag = models.BooleanField(_("Filter by tag"), default=True)
    filter_by_author = models.BooleanField(_("Filter by author"), default=False)

    tagged_title = None
    in_category_title = None
    authored_by_title = None

    # Routes listed in the breadcrumbs of a tag or category filter, if the page has them.
    tags_route = None
    categories_route = None

    # Blog names the taxonomy in the breadcrumb ("Tags" > "sport"); events shows the full title.
    breadcrumb_shows_taxonomy = True

    class Meta:
        abstract = True

    @property
    def filter_locale(self):
        return self.locale

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        posts = self.posts

        extra_breadcrumbs = None
        extra_title = ""

        tag = request.GET.get("tag")
        if tag:
            tag = get_object_or_404(apps.get_model("sites_conformes_core", "Tag"), slug=tag)
            posts = posts.filter(tags=tag)
            extra_title = self.tagged_title % {"tag": tag}
            extra_breadcrumbs = self.filter_breadcrumbs(tag, extra_title, self.tags_route, _("Tags"))

        category = request.GET.get("category")
        if category:
            category = get_object_or_404(
                apps.get_model("sites_conformes_core", "Category"), slug=category, locale=self.filter_locale
            )
            posts = posts.filter(categories=category)
            extra_title = self.in_category_title % {"category": category.name}
            extra_breadcrumbs = self.filter_breadcrumbs(
                category.name, extra_title, self.categories_route, _("Categories")
            )

        source = request.GET.get("source")
        if source:
            source = get_object_or_404(apps.get_model("sites_conformes_blog", "Organization"), slug=source)
            posts = posts.filter(authors__organization=source)
            extra_title = self.authored_by_title + f" {source.name}"
            extra_breadcrumbs = self.filter_breadcrumbs(extra_title, extra_title)

        author = request.GET.get("author")
        if author:
            author = get_object_or_404(apps.get_model("sites_conformes_blog", "Person"), id=author)
            posts = posts.filter(authors=author)
            extra_title = self.authored_by_title + f" {author.name}"
            extra_breadcrumbs = self.filter_breadcrumbs(extra_title, extra_title)

        posts, extra_title = self.apply_extra_filters(request, posts, context, extra_title)

        paginator = Paginator(posts, self.posts_per_page)

        context["posts"] = paginator.get_page(request.GET.get("page"))
        context["current_category"] = category
        context["current_tag"] = tag
        context["current_source"] = source
        context["current_author"] = author
        context["paginator"] = paginator
        context["extra_title"] = extra_title

        context["categories"] = self.get_categories()
        context["category_groups"] = self.get_category_groups()
        context["authors"] = self.get_authors()
        context["sources"] = self.get_sources()
        context["tags"] = self.get_tags()

        if extra_breadcrumbs:
            context["extra_breadcrumbs"] = extra_breadcrumbs

        return context

    def apply_extra_filters(self, request, posts, context, extra_title):
        """Hook for the filters specific to one page type (year, date range)."""
        return posts, extra_title

    def filter_breadcrumbs(self, current, extra_title, route_name=None, route_title=""):
        links = [{"url": self.get_url(), "title": self.title}]
        if route_name and self.breadcrumb_shows_taxonomy:
            links.append({"url": f"{self.get_url()}{self.reverse_subpage(route_name)}", "title": route_title})
        return {"links": links, "current": current if self.breadcrumb_shows_taxonomy else extra_title}

    def get_authors(self) -> models.QuerySet:
        ids = self.posts.specific().values_list("authors", flat=True)
        return apps.get_model("sites_conformes_blog", "Person").objects.filter(id__in=ids).order_by("name")

    def get_categories(self) -> models.QuerySet:
        ids = self.posts.specific().values_list("categories", flat=True)
        return apps.get_model("sites_conformes_core", "Category").objects.filter(id__in=ids).order_by("name")

    def get_sources(self) -> models.QuerySet:
        ids = self.posts.specific().values_list("authors__organization", flat=True)
        return apps.get_model("sites_conformes_blog", "Organization").objects.filter(id__in=ids).order_by("name")

    def get_tags(self) -> models.QuerySet:
        ids = self.posts.specific().values_list("tags", flat=True)
        return apps.get_model("sites_conformes_core", "Tag").objects.filter(id__in=ids).order_by("name")
