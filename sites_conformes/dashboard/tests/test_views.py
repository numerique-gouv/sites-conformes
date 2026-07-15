from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.models import ContentPage
from sites_conformes.dashboard.notifications import get_all_notifications

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
    mock_get.side_effect = Exception("Network error")

    self.client.force_login(self.admin)
    response = self.client.get("/cms-admin/")
    self.assertNotContains(response, "cmsfr-fr-notice")


class TestGetAllNotifications(TestCase):
    def setUp(self):
        cache.clear()

    @patch("sites_conformes.dashboard.notifications.requests.get")
    def test_second_call_uses_cache(self, mock_get):
        """La deuxième requête utilise le cache et n'appelle pas requests.get."""
        mock_get.return_value.json.return_value = {"items": []}
        mock_get.return_value.raise_for_status = MagicMock()

        get_all_notifications()
        get_all_notifications()

        self.assertEqual(mock_get.call_count, 2)
