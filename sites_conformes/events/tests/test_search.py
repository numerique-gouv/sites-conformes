from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from wagtail.models import Page
from wagtail.rich_text import RichText
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.events.models import EventEntryPage, EventsIndexPage

User = get_user_model()


class EventsSearchResultsTestCase(WagtailPageTestCase):
    def setUp(self):
        home_page = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")

        # Common body for the two pages
        body = []

        text_raw = """<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>"""
        body.append(("paragraph", RichText(text_raw)))

        self.admin.save()
        self.events_index = home_page.add_child(
            instance=EventsIndexPage(
                title="Calendrier des événements",
                body=body,
                slug="events-index",
                owner=self.admin,
            )
        )
        self.events_index.save_revision().publish()
        self.event_page = self.events_index.add_child(
            instance=EventEntryPage(
                title="Page d’événement",
                body=body,
                slug="event-entry",
                owner=self.admin,
            )
        )
        self.event_page.save_revision().publish()
        call_command("update_index")

    def test_search_events_index_is_found(self):
        search_url = reverse("cms_search")
        response = self.client.get(f"{search_url}?q=Lorem")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Calendrier des événements")

    def test_search_event_entry_is_found(self):
        search_url = reverse("cms_search")
        response = self.client.get(f"{search_url}?q=Lorem")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page d’événement")
