import datetime

from django.core.paginator import Paginator
from django.db import models
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import get_language, gettext_lazy as _
from icalendar import Calendar, Event, vText
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from modelcluster.tags import ClusterTaggableManager
from taggit.models import TaggedItemBase
from wagtail.admin.panels import FieldPanel, FieldRowPanel, MultiFieldPanel
from wagtail.api import APIField
from wagtail.contrib.routable_page.models import RoutablePageMixin, path
from wagtail.search import index

from sites_conformes.blog.models import AbstractAuthoredIndexPage, PersonSerializer
from sites_conformes.core.abstract import SitesFacilesBasePage
from sites_conformes.core.models import Category, CategorySerializer, CmsDsfrConfig
from sites_conformes.events.forms import EventSearchForm


class EventsIndexPage(AbstractAuthoredIndexPage):
    tagged_title = _("Events tagged with %(tag)s")
    in_category_title = _("Events in category %(category)s")
    written_by_title = _("Events created by")

    settings_panels = SitesFacilesBasePage.settings_panels + [
        FieldPanel("posts_per_page"),
        MultiFieldPanel(
            [
                FieldPanel("filter_by_category"),
                FieldPanel("filter_by_tag"),
                FieldPanel("filter_by_author"),
                FieldPanel("filter_by_source"),
            ],
            heading=_("Show filters"),
        ),
    ]

    subpage_types = ["sites_conformes_events.EventEntryPage"]

    class Meta:
        verbose_name = _("Event calendar index")

    @property
    def posts(self):
        today = timezone.now().date()
        return (
            EventEntryPage.objects.descendant_of(self)
            .live()
            .filter(event_date_end__date__gte=today)
            .order_by("event_date_start")
            .select_related("owner")
            .prefetch_related("tags", "categories", "date__year")
        )

    @property
    def past_events(self):
        today = timezone.now().date()
        return (
            EventEntryPage.objects.descendant_of(self)
            .live()
            .filter(event_date_end__date__lte=today)
            .order_by("-event_date_start")
            .select_related("owner")
            .prefetch_related("tags", "categories", "date__year")
        )

    def apply_filters(self, request: HttpRequest, posts: models.QuerySet) -> tuple[models.QuerySet, dict]:
        posts, context = super().apply_filters(request, posts)

        date_from = request.GET.get("date_from", "")
        if date_from:
            posts = posts.filter(event_date_end__date__gte=date_from)
            context["current_date_from"] = datetime.datetime.strptime(date_from, "%Y-%m-%d").date()

        date_to = request.GET.get("date_to", "")
        if date_to:
            posts = posts.filter(event_date_start__date__lte=date_to)
            context["current_date_to"] = datetime.datetime.strptime(date_to, "%Y-%m-%d").date()

        context["form"] = EventSearchForm(initial={"date_from": date_from, "date_to": date_to})
        return posts, context

    @path("ical/")
    def ical_view(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """
        Render the full calendar as an iCal file
        """
        cal = Calendar()

        cms_settings = CmsDsfrConfig.for_request(request=request)
        site_name = cms_settings.site_title
        language_code = get_language()

        # See https://www.kanzaki.com/docs/ical/prodid.html
        prodid = [
            "-",
            f"{site_name} – {self.title}",
            "Sites Conformes",
            language_code.upper(),
        ]

        cal.add("prodid", "//".join(prodid))
        cal.add("version", "2.0")

        dtstamp = timezone.now()
        for entry in self.posts:
            event = entry.ical_event(dtstamp)
            cal.add_component(event)

        response = HttpResponse(cal.to_ical(), content_type="text/calendar")
        response["Content-Disposition"] = f'attachment; filename="{slugify(site_name)}.ics"'
        return response

    @path("archives/")
    def archives_view(self, request):
        extra_title = _("Past events")

        past_events = self.past_events

        year = request.GET.get("year")
        if year:
            past_events = past_events.filter(event_date_start__year=year)
            extra_title = _("Events published in %(year)s") % {"year": year}
            year = int(year)

        extra_breadcrumbs = {
            "links": [
                {"url": self.get_url(), "title": self.title},
            ],
            "current": extra_title,
        }
        # Pagination
        page_number = request.GET.get("page")
        page_size = self.posts_per_page

        paginator = Paginator(past_events, page_size)  # Show <page_size> posts per page
        past_events = paginator.get_page(page_number)

        return self.render(
            request,
            context_overrides={
                "extra_title": extra_title,
                "extra_breadcrumbs": extra_breadcrumbs,
                "posts": past_events,
                "years": sorted(set(self.past_events.values_list("event_date_start__year", flat=True)), reverse=True),
                "paginator": paginator,
                "current_year": year,
            },
            template="sites_conformes_events/events_archive_page.html",
        )


class EventEntryPage(RoutablePageMixin, SitesFacilesBasePage):
    tags = ClusterTaggableManager(through="TagEventEntryPage", blank=True)

    categories = ParentalManyToManyField(
        "sites_conformes_core.Category",
        through="CategoryEventEntryPage",
        blank=True,
        verbose_name=_("Categories"),
    )

    date = models.DateTimeField(verbose_name=_("Post date"), default=timezone.now)
    event_date_start = models.DateTimeField(verbose_name=_("Event start date"), default=timezone.now)
    event_date_end = models.DateTimeField(verbose_name=_("Event end date"), default=timezone.now)

    location = models.CharField(max_length=200, verbose_name=_("Location"), blank=True, null=True)
    registration_url = models.URLField(
        verbose_name=_("Registration URL"),
        help_text=_("Max length: 2000 characters."),
        max_length=2000,
        blank=True,
        null=True,
    )

    authors = ParentalManyToManyField(
        "sites_conformes_blog.Person", blank=True, help_text=_("Author entries can be created in Snippets > Persons")
    )

    parent_page_types = ["sites_conformes_events.EventsIndexPage"]
    subpage_types = []

    search_fields = SitesFacilesBasePage.search_fields + [
        index.SearchField("categories"),
        index.SearchField("event_date_start"),
        index.SearchField("event_date_end"),
        index.SearchField("location"),
        index.SearchField("registration_url"),
    ]

    settings_panels = SitesFacilesBasePage.settings_panels + [
        FieldPanel("authors"),
        FieldPanel("date"),
        MultiFieldPanel(
            [
                FieldRowPanel(
                    [
                        FieldPanel("event_date_start"),
                        FieldPanel("event_date_end"),
                    ],
                    classname="label-above",
                ),
                FieldPanel("location"),
                FieldPanel("registration_url"),
            ],
            _("Event date and place"),
        ),
        MultiFieldPanel(
            [
                FieldRowPanel(
                    [
                        FieldPanel("go_live_at"),
                        FieldPanel("expire_at"),
                    ],
                    classname="label-above",
                ),
            ],
            _("Scheduled publishing"),
            classname="publishing",
        ),
        MultiFieldPanel(
            [
                FieldPanel("categories"),
                FieldPanel("tags"),
            ],
            heading=_("Tags and Categories"),
        ),
    ]

    api_fields = SitesFacilesBasePage.api_fields + [
        APIField("tags"),
        APIField("event_categories", serializer=CategorySerializer(many=True, source="categories")),
        APIField("authors", serializer=PersonSerializer(many=True)),
        APIField("event_date_start"),
        APIField("event_date_end"),
        APIField("location"),
        APIField("registration_url"),
        APIField("go_live_at"),
        APIField("expire_at"),
    ]

    def get_absolute_url(self):
        return self.url

    def ical_event(self, dtstamp=None):
        """
        Formats the event as an iCalendar event
        """
        if not dtstamp:
            dtstamp = timezone.now()

        event = Event()
        event.add("summary", self.title)
        event.add("dtstart", self.event_date_start)
        event.add("dtend", self.event_date_end)
        event.add("dtstamp", dtstamp)
        event.add("uid", str(self.pk))
        event["location"] = vText(self.location)

        return event

    @path("ical/")
    def ical_view(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """
        Render the event as an iCal file
        """
        cal = Calendar()

        cms_settings = CmsDsfrConfig.for_request(request=request)
        site_name = cms_settings.site_title
        language_code = get_language()

        title = f"{site_name} – {self.title}"

        # See https://www.kanzaki.com/docs/ical/prodid.html for format
        prodid = [
            "-",
            title,
            "Sites Conformes",
            language_code.upper(),
        ]

        cal.add("prodid", "//".join(prodid))
        cal.add("version", "2.0")

        event = self.ical_event()
        cal.add_component(event)

        response = HttpResponse(cal.to_ical(), content_type="text/calendar")
        response["Content-Disposition"] = f'attachment; filename="{slugify(title)}.ics"'
        return response

    class Meta:
        verbose_name = _("Event page")


class TagEventEntryPage(TaggedItemBase):
    content_object = ParentalKey("EventEntryPage", related_name="event_entry_tags")


class CategoryEventEntryPage(models.Model):
    category = models.ForeignKey(Category, related_name="+", verbose_name=_("Category"), on_delete=models.CASCADE)
    page = ParentalKey("EventEntryPage", related_name="event_entry_categories")
    panels = [FieldPanel("category")]

    def __str__(self):
        return self.category
