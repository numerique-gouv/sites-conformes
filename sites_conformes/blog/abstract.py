from django.apps import apps
from django.db import models
from django.db.models import BooleanField, QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _

from sites_conformes.core.abstract import AbstractIndexPage


class AbstractAuthoredIndexPage(AbstractIndexPage):
    filter_by_author = models.BooleanField(_("Filter by author"), default=False)
    filter_by_source = models.BooleanField(
        _("Filter by source"), help_text=_("The source is the organization of the post author"), default=False
    )

    written_by_title = _("Pages written by")

    class Meta:
        abstract = True

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context.update(authors=self.get_authors(), sources=self.get_sources())
        return context

    def apply_filters(self, request: HttpRequest, posts: QuerySet) -> tuple[QuerySet, dict]:
        posts, context = super().apply_filters(request, posts)
        context.update(current_source=None, current_author=None)

        slug = request.GET.get("source")
        if slug:
            source = get_object_or_404(apps.get_model("sites_conformes_blog", "Organization"), slug=slug)
            posts = posts.filter(authors__organization=source)
            title = f"{self.written_by_title} {source.name}"
            context.update(current_source=source, extra_title=title, extra_breadcrumbs=self.filter_breadcrumbs(title))

        author_id = request.GET.get("author")
        if author_id:
            author = get_object_or_404(apps.get_model("sites_conformes_blog", "Person"), id=author_id)
            posts = posts.filter(authors=author)
            title = f"{self.written_by_title} {author.name}"
            context.update(current_author=author, extra_title=title, extra_breadcrumbs=self.filter_breadcrumbs(title))

        return posts, context

    def get_authors(self) -> QuerySet:
        ids = self.posts.specific().values_list("authors", flat=True)
        return apps.get_model("sites_conformes_blog", "Person").objects.filter(id__in=ids).order_by("name")

    def get_sources(self) -> QuerySet:
        ids = self.posts.specific().values_list("authors__organization", flat=True)
        return apps.get_model("sites_conformes_blog", "Organization").objects.filter(id__in=ids).order_by("name")

    @property
    def show_filters(self) -> bool | BooleanField:
        return self.filter_by_category or self.filter_by_tag or self.filter_by_author or self.filter_by_source
