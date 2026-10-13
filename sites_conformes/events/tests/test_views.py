from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.models import Tag
from sites_conformes.events.models import EventEntryPage, EventsIndexPage

User = get_user_model()


class EventsTestCase(WagtailPageTestCase):
    def setUp(self):
        self.home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()
        self.events_index_page = self.home.add_child(
            instance=EventsIndexPage(
                title="Agenda",
                slug="events",
                owner=self.admin,
            )
        )
        self.events_index_page.save()

        self.past_event = self.events_index_page.add_child(
            instance=EventEntryPage(
                title="Événement passé",
                date=timezone.now() - timedelta(days=365),
                event_date_start=timezone.now() - timedelta(days=365),
                event_date_end=timezone.now() - timedelta(days=360),
                owner=self.admin,
            )
        )
        self.past_event.save()

        self.current_event = self.events_index_page.add_child(
            instance=EventEntryPage(
                title="Événement en cours",
                date=timezone.now() - timedelta(days=5),
                event_date_start=timezone.now() - timedelta(days=5),
                event_date_end=timezone.now() + timedelta(days=5),
                owner=self.admin,
            )
        )
        self.current_event.save()

        self.future_event = self.events_index_page.add_child(
            instance=EventEntryPage(
                title="Événement futur",
                date=timezone.now(),
                event_date_start=timezone.now() + timedelta(days=360),
                event_date_end=timezone.now() + timedelta(days=365),
                owner=self.admin,
            )
        )
        self.future_event.save()

    def test_events_index_page_is_renderable(self):
        self.assertPageIsRenderable(self.events_index_page)

    def test_events_index_page_has_minimal_content(self):
        response = self.client.get(self.events_index_page.url)
        self.assertEqual(response.status_code, 200)

        self.assertInHTML(
            "<title>Agenda — Titre du site</title>",
            response.content.decode(),
        )

    def test_events_index_page_has_current_and_future_events(self):
        response = self.client.get(self.events_index_page.url)

        self.assertNotContains(
            response,
            "Événement passé",
        )

        self.assertContains(
            response,
            "Événement en cours",
        )
        self.assertContains(
            response,
            "Événement futur",
        )

    def test_events_index_page_has_accessible_date_filters(self):
        response = self.client.get(self.events_index_page.url)

        self.assertContains(response, '<form method="get"')
        self.assertContains(response, '<fieldset class="fr-fieldset" aria-labelledby="events-period-legend">')
        self.assertContains(response, "Filtrer par période")
        self.assertContains(response, '<button type="submit" class="fr-btn">Filtrer</button>', html=True)
        self.assertContains(response, 'aria-live="polite"')
        self.assertContains(response, "2 événements trouvés")

    def test_events_index_page_filters_by_date(self):
        date_from = (timezone.now() + timedelta(days=300)).date().isoformat()
        response = self.client.get(self.events_index_page.url, {"date_from": date_from})

        self.assertNotContains(response, "Événement en cours")
        self.assertContains(response, "Événement futur")
        self.assertContains(response, "1 événement trouvé")

    def test_events_index_page_ignores_invalid_date(self):
        response = self.client.get(self.events_index_page.url, {"date_from": "invalid"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2 événements trouvés")

    def test_events_index_page_rejects_end_date_before_start_date(self):
        response = self.client.get(self.events_index_page.url, {"date_from": "2026-06-10", "date_to": "2026-06-01"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "fr-input-group--error")
        self.assertContains(response, "La date de fin doit être identique ou postérieure à la date de début.")

    def test_events_index_page_date_filters_keep_other_filters(self):
        Tag.objects.create(name="Atelier", slug="atelier")
        response = self.client.get(self.events_index_page.url, {"tag": "atelier"})

        self.assertContains(response, '<input type="hidden" name="tag" value="atelier">', html=True)

    def test_events_archives_have_only_finished_events(self):
        response = self.client.get(self.events_index_page.url + "archives/")

        self.assertContains(
            response,
            "Événement passé",
        )

        self.assertNotContains(
            response,
            "Événement en cours",
        )

        self.assertNotContains(
            response,
            "Événement futur",
        )

    def test_event_is_renderable(self):
        self.assertPageIsRenderable(self.current_event)

    def test_event_has_minimal_content(self):
        response = self.client.get(self.current_event.url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "<title>Événement en cours — Titre du site</title>",
        )

    def test_events_index_has_ical_feed(self):
        response = self.client.get(self.events_index_page.url + "ical/")
        self.assertEqual(response.status_code, 200)
