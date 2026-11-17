from django.contrib.auth import get_user_model
from django.urls import reverse
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.models import Category
from sites_conformes.events.models import EventEntryPage, EventsIndexPage

User = get_user_model()


class EventEntryPageAPITest(WagtailPageTestCase):
    def test_categories_are_exposed_under_their_historical_key(self):
        home = Page.objects.get(slug="home")
        index = home.add_child(instance=EventsIndexPage(title="Agenda", slug="agenda"))
        category = Category.objects.create(name="Formation", slug="formation")
        entry = index.add_child(instance=EventEntryPage(title="Atelier", slug="atelier", categories=[category]))

        response = self.client.get(reverse("wagtailapi:pages:detail", kwargs={"pk": entry.id}))

        self.assertEqual([c["slug"] for c in response.json()["event_categories"]], [category.slug])
