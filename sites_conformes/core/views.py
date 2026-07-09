from django.apps import apps
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, TemplateView
from unidecode import unidecode
from wagtail.models import Page, Site

from sites_conformes.core.models import ContentPage, Tag


class SearchResultsView(ListView):
    """
    Search results page view.

    The search should only return pages that are:

    - live
    - part of the current site
    - in the current locale

    If user is anonymous, only public pages are returned.

    If there is no result, an empty page list is returned.
    """

    model = Page
    template_name = "sites_conformes_core/search_results.html"

    def get_template_names(self):
        if apps.is_installed("faceted_search"):
            return ["faceted_search/search_results.html"]
        return [self.template_name]

    def get_searchable_queryset(self, site):
        root_page = site.root_page.localized
        queryset = Page.objects.descendant_of(root_page, inclusive=True).live()
        if not self.request.user.is_authenticated:
            queryset = queryset.public()
        return queryset

    def filter_search_queryset(self, queryset, site):
        """Extension point for fork apps. Return the filtered queryset."""
        return queryset

    def get_search_filter_context(self, site):
        """Extension point for fork apps. Return template context for the filter sidebar."""
        return {}

    def get_queryset(self):
        site = Site.find_for_request(self.request)
        query = self.request.GET.get("q", None)
        if not query:
            return Page.objects.none()

        object_list = self.get_searchable_queryset(site)
        object_list = self.filter_search_queryset(object_list, site)
        return object_list.search(query)

    def get_context_data(self, **kwargs):
        context = super(SearchResultsView, self).get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q")
        site = Site.find_for_request(self.request)
        context.update(self.get_search_filter_context(site))
        return context


class TagsListView(TemplateView):
    template_name = "sites_conformes_core/tags_list_page.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        tags = Tag.objects.tags_with_usecount(1)

        tags_by_first_letter = {}
        for tag in tags:
            first_letter = unidecode(tag.slug[0].upper())
            if first_letter not in tags_by_first_letter:
                tags_by_first_letter[first_letter] = []
            tags_by_first_letter[first_letter].append(tag)

        context["sorted_tags"] = tags_by_first_letter

        title = _("Tags")
        context["title"] = title
        script_name = settings.FORCE_SCRIPT_NAME or ""
        root_dir = f"{script_name.rstrip('/')}/" if script_name else "/"
        context["breadcrumb"] = {
            "links": [],
            "current": title,
            "root_dir": root_dir,
        }
        context["search_description"] = _("List of all the tags.")

        return context


class TagView(ListView):
    template_name = "sites_conformes_core/tag_page.html"
    model = ContentPage
    paginate_by = 10

    def get_queryset(self, **kwargs):
        tag_slug = self.kwargs.get("tag")
        return ContentPage.objects.filter(tags__slug=tag_slug, live=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tag_slug = self.kwargs.get("tag")

        tag = get_object_or_404(Tag, slug=tag_slug)
        context["tag"] = tag

        title = _("Pages tagged with {tag}").format(tag=tag.name)
        context["title"] = title
        context["breadcrumb"] = {
            "links": [
                {"url": reverse("global_tags_list"), "title": _("Tags")},
            ],
            "current": title,
        }

        context["search_description"] = _("List of pages tagged with {tag}").format(tag=tag.name)

        return context


class SiteMapView(TemplateView):
    """
    Readable sitemap for accessibility
    (different than the SEO-oriented sitemap.xml)
    """

    template_name = "sites_conformes_core/sitemap_page.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        site = Site.find_for_request(self.request)
        context["home_page"] = site.root_page

        script_name = settings.FORCE_SCRIPT_NAME or ""
        root_dir = f"{script_name.rstrip('/')}/" if script_name else "/"
        title = _("Sitemap")
        context["title"] = title

        context["breadcrumb"] = {
            "links": [],
            "current": title,
            "root_dir": root_dir,
        }
        return context
