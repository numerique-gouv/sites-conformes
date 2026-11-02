from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.blog.tests.factories import CategoryFactory, PersonFactory
from sites_conformes.events.models import EventEntryPage, EventsIndexPage

User = get_user_model()


class EventsFiltersTestCase(WagtailPageTestCase):
    def setUp(self):
        home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.events_index_page = home.add_child(instance=EventsIndexPage(title="Agenda", slug="agenda"))

        self.author = PersonFactory(name="Jeanne Martin")
        self.category = CategoryFactory(name="Ateliers")

        self.workshop = self.add_event("Atelier d’écriture")
        self.workshop.event_categories.add(self.category)
        self.workshop.authors.add(self.author)
        self.workshop.save_revision().publish()

        self.other_event = self.add_event("Conférence")

    def add_event(self, title):
        return self.events_index_page.add_child(
            instance=EventEntryPage(
                title=title,
                date=timezone.now(),
                event_date_start=timezone.now() + timedelta(days=1),
                event_date_end=timezone.now() + timedelta(days=2),
                owner=self.admin,
            )
        )

    def get_index(self, **params):
        return self.client.get(self.events_index_page.url, params)

    def test_filter_by_category(self):
        response = self.get_index(category=self.category.slug)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Atelier d’écriture")
        self.assertNotContains(response, "Conférence")
        self.assertEqual(
            response.context["extra_title"], gettext("Events in category %(category)s") % {"category": "Ateliers"}
        )

    def test_filter_by_source(self):
        response = self.get_index(source=self.author.organization.slug)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Atelier d’écriture")
        self.assertNotContains(response, "Conférence")

    def test_filter_by_author(self):
        response = self.get_index(author=self.author.pk)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Atelier d’écriture")
        self.assertNotContains(response, "Conférence")

    def test_unknown_filters_return_404(self):
        self.assertEqual(self.get_index(category="inconnue").status_code, 404)
        self.assertEqual(self.get_index(source="inconnue").status_code, 404)
        self.assertEqual(self.get_index(author=999999).status_code, 404)

    def test_event_ical_export(self):
        response = self.client.get(self.workshop.url + "ical/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/calendar")
        self.assertRegex(response["Content-Disposition"], r'^attachment; filename=".+\.ics"$')
        content = response.content.decode()
        self.assertIn("BEGIN:VEVENT", content)
        self.assertIn("Atelier d’écriture", content)
