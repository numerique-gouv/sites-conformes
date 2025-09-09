import datetime

from django.core.paginator import Paginator
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
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
from wagtail.models.i18n import Locale
from wagtail.search import index

from blog.models import Category, CategorySerializer, Organization, Person, PersonSerializer
from content_manager.abstract import SitesFacilesBasePage
from content_manager.models import CmsDsfrConfig, Tag
from events.forms import EventSearchForm


class EventsIndexPage(RoutablePageMixin, SitesFacilesBasePage):
    posts_per_page = models.PositiveSmallIntegerField(
        default=10,
        validators=[MaxValueValidator(100), MinValueValidator(1)],
        verbose_name=_("Events per page"),
    )

    # Filters
    filter_by_category = models.BooleanField(_("Filter by category"), default=True)
    filter_by_tag = models.BooleanField(_("Filter by tag"), default=True)
    filter_by_author = models.BooleanField(_("Filter by author"), default=False)
    filter_by_source = models.BooleanField(
        _("Filter by source"), help_text=_("The source is the organization of the event author"), default=False
    )

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

    subpage_types = ["events.EventEntryPage"]

    class Meta:
        verbose_name = _("Event calendar index")

    @property
    def posts(self):
        # Get list of event pages that are descendants of this page
        today = timezone.now().date()
        entries = (
            EventEntryPage.objects.descendant_of(self)
            .live()
            .filter(event_date_end__date__gte=today)
            .order_by("event_date_start")
            .select_related("owner")
            .prefetch_related("tags", "event_categories", "date__year")
        )
        return entries

    @property
    def past_events(self):
        today = timezone.now().date()
        entries = (
            EventEntryPage.objects.descendant_of(self)
            .live()
            .filter(event_date_end__date__lte=today)
            .order_by("-event_date_start")
            .select_related("owner")
            .prefetch_related("tags", "event_categories", "date__year")
        )
        return entries

    def get_context(self, request, *args, **kwargs):
        context = super(EventsIndexPage, self).get_context(request, *args, **kwargs)
        posts = self.posts
        locale = Locale.objects.get(language_code=get_language())

        extra_breadcrumbs = None
        extra_title = ""

        tag = request.GET.get("tag")
        if tag:
            tag = get_object_or_404(Tag, slug=tag)
            posts = posts.filter(tags=tag)
            extra_title = _("Events tagged with %(tag)s") % {"tag": tag}
            extra_breadcrumbs = {
                "links": [
                    {"url": self.get_url(), "title": self.title},
                ],
                "current": extra_title,
            }

        category = request.GET.get("category")
        if category:
            category = get_object_or_404(Category, slug=category, locale=locale)
            posts = posts.filter(event_categories=category)
            extra_title = _("Events in category %(category)s") % {"category": category.name}
            extra_breadcrumbs = {
                "links": [
                    {"url": self.get_url(), "title": self.title},
                ],
                "current": extra_title,
            }

        source = request.GET.get("source")
        if source:
            source = get_object_or_404(Organization, slug=source)
            posts = posts.filter(authors__organization=source)
            extra_title = _("Events created by") + f" {source.name}"
            extra_breadcrumbs = {
                "links": [
                    {"url": self.get_url(), "title": self.title},
                ],
                "current": extra_title,
            }

        author = request.GET.get("author")
        if author:
            author = get_object_or_404(Person, id=author)
            extra_title = _("Events created by") + f" {author.name}"
            extra_breadcrumbs = {
                "links": [
                    {"url": self.get_url(), "title": self.title},
                ],
                "current": extra_title,
            }
            posts = posts.filter(authors=author)

        date_from = request.GET.get("date_from", "")
        if date_from:
            posts = posts.filter(event_date_end__date__gte=date_from)
            context["current_date_from"] = datetime.datetime.strptime(date_from, "%Y-%m-%d").date()

        date_to = request.GET.get("date_to", "")
        if date_to:
            posts = posts.filter(event_date_start__date__lte=date_to)
            context["current_date_to"] = datetime.datetime.strptime(date_to, "%Y-%m-%d").date()

        form = EventSearchForm(initial={"date_from": date_from, "date_to": date_to})

        # Pagination
        page_number = request.GET.get("page")
        page_size = self.posts_per_page

        paginator = Paginator(posts, page_size)  # Show <page_size> posts per page
        posts = paginator.get_page(page_number)

        context["posts"] = posts
        context["current_category"] = category
        context["current_tag"] = tag
        context["current_source"] = source
        context["current_author"] = author
        context["paginator"] = paginator
        context["extra_title"] = extra_title

        # Filters
        context["form"] = form
        context["categories"] = self.get_categories()
        context["authors"] = self.get_authors()
        context["sources"] = self.get_sources()
        context["tags"] = self.get_tags()

        if extra_breadcrumbs:
            context["extra_breadcrumbs"] = extra_breadcrumbs

        return context

    def get_authors(self) -> models.QuerySet:
        ids = self.posts.specific().values_list("authors", flat=True)
        return Person.objects.filter(id__in=ids).order_by("name")

    def get_categories(self) -> models.QuerySet:
        ids = self.posts.specific().values_list("event_categories", flat=True)
        return Category.objects.filter(id__in=ids).order_by("name")

    def get_sources(self) -> models.QuerySet:
        ids = self.posts.specific().values_list("authors__organization", flat=True)
        return Organization.objects.filter(id__in=ids).order_by("name")

    def get_tags(self) -> models.QuerySet:
        ids = self.posts.specific().values_list("tags", flat=True)
        return Tag.objects.filter(id__in=ids).order_by("name")

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
            "Sites faciles",
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
            template="events/events_archive_page.html",
        )


class EventEntryPage(RoutablePageMixin, SitesFacilesBasePage):
    tags = ClusterTaggableManager(through="TagEventEntryPage", blank=True)

    event_categories = ParentalManyToManyField(
        "blog.Category",
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
        "blog.Person", blank=True, help_text=_("Author entries can be created in Snippets > Persons")
    )

    parent_page_types = ["events.EventsIndexPage"]
    subpage_types = []

    search_fields = SitesFacilesBasePage.search_fields + [
        index.SearchField("event_categories"),
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
                FieldPanel("event_categories"),
                FieldPanel("tags"),
            ],
            heading=_("Tags and Categories"),
        ),
    ]

    api_fields = SitesFacilesBasePage.api_fields + [
        APIField("tags"),
        APIField("event_categories", serializer=CategorySerializer(many=True)),
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
            "Sites faciles",
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
