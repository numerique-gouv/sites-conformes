from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from dashboard.utils import get_all_notifications, is_last_version, push_version_notification


@override_settings(
    INFORMATION_URL="https://example.com/notifications.json",
    LATEST_RELEASE_URL="https://api.github.com/repos/test/test/releases/latest",
)
class TestIsLastVersion(TestCase):
    def test_same_version_is_last(self):
        self.assertTrue(is_last_version("3.0.0", "3.0.0"))

    def test_older_version_is_not_last(self):
        self.assertFalse(is_last_version("2.5.2", "3.0.0"))

    def test_newer_version_is_last(self):
        self.assertTrue(is_last_version("3.1.0", "3.0.0"))

    def test_patch_version_comparison(self):
        self.assertFalse(is_last_version("3.0.0", "3.0.1"))


@override_settings(
    INFORMATION_URL="https://raw.githubusercontent.com/Luzzzi/test-information-panel/main/test.json",
    LATEST_RELEASE_URL="https://api.github.com/repos/test/test/releases/latest",
)
class TestPushVersionNotification(TestCase):
    @patch("dashboard.utils.requests.get")
    @patch("dashboard.utils.actual_version", "3.0.0")
    def test_no_notification_if_up_to_date(self, mock_get):

        mock_get.return_value.json.return_value = {"tag_name": "v3.0.0"}
        mock_get.return_value.raise_for_status = MagicMock()

        items = push_version_notification([])
        self.assertEqual(items, [])

    @patch("dashboard.utils.requests.get")
    @patch("dashboard.utils.actual_version", "2.9.0")
    def test_notification_if_outdated(self, mock_get):

        mock_get.return_value.json.return_value = {"tag_name": "v3.0.0"}
        mock_get.return_value.raise_for_status = MagicMock()

        items = push_version_notification([])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["type"], "info")
        self.assertIn("3.0.0", items[0]["title"])

    @patch("dashboard.utils.requests.get")
    def test_no_notification_if_request_fails(self, mock_get):

        mock_get.side_effect = Exception("Network error")

        items = push_version_notification([])
        self.assertEqual(items, [])


@override_settings(
    INFORMATION_URL="https://raw.githubusercontent.com/Luzzzi/test-information-panel/main/test.json",
    LATEST_RELEASE_URL="https://api.github.com/repos/test/test/releases/latest",
)
class TestGetAllNotifications(TestCase):
    def setUp(self):
        cache.clear()

    @patch("dashboard.utils.requests.get")
    def test_empty_if_json_not_found(self, mock_get):
        """Rien ne s'affiche si le fichier notifications.json est introuvable."""

        mock_get.side_effect = Exception("404 Not Found")

        items = get_all_notifications()
        json_items = [i for i in items if "end_date" in i]
        self.assertEqual(json_items, [])

    @patch("dashboard.utils.requests.get")
    def test_empty_if_request_error(self, mock_get):
        """Rien ne s'affiche si la requête renvoie une erreur HTTP."""

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("500 Server Error")
        mock_get.return_value = mock_response

        items = get_all_notifications()
        json_items = [i for i in items if "end_date" in i]
        self.assertEqual(json_items, [])

    @patch("dashboard.utils.requests.get")
    def test_item_displayed_if_end_date_in_future(self, mock_get):
        """Une notification s'affiche si end_date est dans le futur."""
        future_date = (date.today() + timedelta(days=10)).isoformat()
        mock_get.return_value.json.return_value = {
            "items": [
                {
                    "type": "info",
                    "title": "Notification de test",
                    "description": "Description",
                    "end_date": future_date,
                }
            ]
        }
        mock_get.return_value.raise_for_status = MagicMock()

        items = get_all_notifications()
        titles = [i["title"] for i in items]
        self.assertIn("Notification de test", titles)

    @patch("dashboard.utils.requests.get")
    def test_item_not_displayed_if_end_date_in_past(self, mock_get):
        """Une notification n'est pas affichée si end_date est dépassée."""

        past_date = (date.today() - timedelta(days=1)).isoformat()
        mock_get.return_value.json.return_value = {
            "items": [
                {
                    "type": "info",
                    "title": "Notification expirée",
                    "description": "Description",
                    "end_date": past_date,
                }
            ]
        }
        mock_get.return_value.raise_for_status = MagicMock()

        items = get_all_notifications()
        titles = [i["title"] for i in items]
        self.assertNotIn("Notification expirée", titles)

    @patch("dashboard.utils.requests.get")
    def test_item_displayed_if_no_end_date(self, mock_get):
        """Une notification sans end_date s'affiche toujours."""

        mock_get.return_value.json.return_value = {
            "items": [
                {
                    "type": "info",
                    "title": "Notification permanente",
                    "description": "Description",
                }
            ]
        }
        mock_get.return_value.raise_for_status = MagicMock()

        items = get_all_notifications()
        titles = [i["title"] for i in items]
        self.assertIn("Notification permanente", titles)

    @patch("dashboard.utils.requests.get")
    def test_item_not_displayed_if_end_date_malformed(self, mock_get):
        """Une notification avec une date malformée n'est pas affichée."""

        mock_get.return_value.json.return_value = {
            "items": [
                {
                    "type": "info",
                    "title": "Notification date invalide",
                    "description": "Description",
                    "end_date": "pas-une-date",
                }
            ]
        }
        mock_get.return_value.raise_for_status = MagicMock()

        items = get_all_notifications()
        titles = [i["title"] for i in items]
        self.assertNotIn("Notification date invalide", titles)
