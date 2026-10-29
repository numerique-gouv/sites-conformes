from datetime import date
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from wagtail.models import Page, Site
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.models import ContentPage
from sites_conformes.dashboard.notifications import get_all_notifications
from sites_conformes.dashboard.views import NotificationPanel, ShortcutsPanel, TutorialsPanel

User = get_user_model()


class DashboardTestCase(WagtailPageTestCase):
    def setUp(self):
        home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()

        self.content_page = home.add_child(
            instance=ContentPage(
                title="Page de contenu",
                slug="content-page",
                owner=self.admin,
            )
        )
        self.content_page.save()

    def test_userbar_is_present_when_logged_in(self):
        url = self.content_page.url
        response = self.client.get(url)
        self.assertNotContains(
            response,
            '<svg class="icon icon-edit w-userbar-icon" aria-hidden="true"><use href="#icon-edit"></use></svg>',
            html=True,
        )

        self.client.force_login(self.admin)
        response = self.client.get(url)
        self.assertContains(
            response,
            '<svg class="icon icon-edit w-userbar-icon" aria-hidden="true"><use href="#icon-edit"></use></svg>',
            html=True,
        )

    @patch("sites_conformes.dashboard.notifications.requests.get")
    def test_information_panel_not_displayed_if_request_fails(self, mock_get):
        """Rien ne s'affiche dans le back-office si la requête vers le JSON échoue."""
        cache.clear()
        mock_get.side_effect = requests.ConnectionError("Network error")

        self.client.force_login(self.admin)
        response = self.client.get("/cms-admin/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="fr-notice')


class TestGetAllNotifications(TestCase):
    def setUp(self):
        cache.clear()

    @patch("sites_conformes.dashboard.notifications.requests.get")
    def test_second_call_uses_cache(self, mock_get):
        """La deuxième requête utilise le cache et n'appelle pas requests.get."""
        mock_get.return_value.json.return_value = {"items": []}
        mock_get.return_value.raise_for_status = MagicMock()

        get_all_notifications()
        calls_after_first = mock_get.call_count
        get_all_notifications()

        self.assertGreater(calls_after_first, 0)
        self.assertEqual(mock_get.call_count, calls_after_first)


class ShortcutsPanelTestCase(TestCase):
    def test_context_links_point_to_default_site(self):
        site = Site.objects.get(is_default_site=True)
        home_pk = site.root_page.pk

        context = ShortcutsPanel().get_context_data()

        self.assertEqual(context["site"], site)
        self.assertEqual(context["home_page_edit"], reverse("wagtailadmin_pages:edit", args=(home_pk,)))
        self.assertEqual(context["pages_list"], reverse("wagtailadmin_explore", args=(home_pk,)))
        self.assertEqual(context["create_page"], reverse("wagtailadmin_pages:add_subpage", args=(home_pk,)))
        self.assertIn(str(site.pk), context["settings_url"])
        self.assertEqual(context["main_menus"], reverse("wagtailsnippets_sites_conformes_menus_mainmenu:list"))


class TutorialsPanelTestCase(TestCase):
    def setUp(self):
        cache.clear()

    @patch("sites_conformes.dashboard.views.requests.get")
    def test_tutorials_are_fetched_and_cached(self, mock_get):
        list_response = MagicMock()
        list_response.json.return_value = {"items": [{"id": 12}]}
        page_response = MagicMock()
        page_response.json.return_value = {
            "title": "Créer une page",
            "preview_image_render": {"full_url": "https://example.com/img.png"},
            "meta": {"html_url": "https://example.com/tuto/"},
        }
        mock_get.side_effect = [list_response, page_response]

        context = TutorialsPanel().get_context_data()

        expected = [
            {"title": "Créer une page", "image": "https://example.com/img.png", "url": "https://example.com/tuto/"}
        ]
        self.assertEqual(context["tutorials"], expected)
        self.assertEqual(cache.get(TutorialsPanel.TUTORIAL_PANEL_CACHE_KEY), expected)

        # Le second appel utilise le cache
        TutorialsPanel().get_context_data()
        self.assertEqual(mock_get.call_count, 2)

    @patch("sites_conformes.dashboard.views.requests.get")
    def test_tutorials_are_empty_if_request_fails(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("Network error")

        context = TutorialsPanel().get_context_data()

        self.assertEqual(context["tutorials"], [])
        self.assertEqual(cache.get(TutorialsPanel.TUTORIAL_PANEL_CACHE_KEY), [])


class NotificationPanelTestCase(TestCase):
    @patch("sites_conformes.dashboard.views.get_all_notifications")
    def test_start_date_is_parsed_when_valid(self, mock_notifications):
        mock_notifications.return_value = [
            {"type": "info", "title": "Valide", "start_date": "2024-05-01"},
            {"type": "info", "title": "Invalide", "start_date": "pas une date"},
            {"type": "info", "title": "Sans date"},
        ]

        notifications = NotificationPanel().get_context_data()["notifications"]

        self.assertEqual(notifications[0]["start_date"], date(2024, 5, 1))
        self.assertEqual(notifications[1]["start_date"], "pas une date")
        self.assertNotIn("start_date", notifications[2])
