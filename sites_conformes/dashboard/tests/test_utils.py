from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings

from dashboard.utils import get_all_notifications, is_last_version, push_version_notification

INFORMATION_URL = settings.INFORMATION_URL
LATEST_RELEASE_URL = settings.LATEST_RELEASE_URL


@override_settings(
    INFORMATION_URL=INFORMATION_URL,
    LATEST_RELEASE_URL=LATEST_RELEASE_URL,
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
    INFORMATION_URL=INFORMATION_URL,
    LATEST_RELEASE_URL=LATEST_RELEASE_URL,
)
class TestPushVersionNotification(TestCase):
    @patch("dashboard.utils.requests.get")
    @patch("dashboard.utils.actual_version", "3.0.0")
    def test_uses_latest_release_url(self, mock_get):
        """Vérifie que la bonne URL est appelée."""
        mock_get.return_value.json.return_value = {"tag_name": "v3.0.0"}
        mock_get.return_value.raise_for_status = MagicMock()

        push_version_notification([])

        mock_get.assert_called_once_with(settings.LATEST_RELEASE_URL, timeout=5)

    @patch("dashboard.utils.requests.get")
    @patch("dashboard.utils.actual_version", "3.0.0")
    def test_no_notification_if_up_to_date(self, mock_get):
        """Aucune notification si la version est à jour."""
        mock_get.return_value.json.return_value = {"tag_name": "v3.0.0"}
        mock_get.return_value.raise_for_status = MagicMock()

        items = push_version_notification([])
        self.assertEqual(items, [])

    @patch("dashboard.utils.requests.get")
    @patch("dashboard.utils.actual_version", "2.9.0")
    def test_notification_if_outdated(self, mock_get):
        """Une notification s'affiche si la version est obsolète."""
        mock_get.return_value.json.return_value = {"tag_name": "v3.0.0"}
        mock_get.return_value.raise_for_status = MagicMock()

        items = push_version_notification([])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["type"], "info")
        self.assertIn("3.0.0", items[0]["title"])

    @patch("dashboard.utils.requests.get")
    def test_no_crash_if_github_unavailable(self, mock_get):
        """GitHub indisponible : retourne la liste inchangée, ne plante pas."""
        mock_get.side_effect = Exception("Connection refused")

        items = push_version_notification([])
        self.assertEqual(items, [])

    @patch("dashboard.utils.requests.get")
    @patch("dashboard.utils.actual_version", "")
    def test_no_crash_if_no_version_number(self, mock_get):
        """Pas de numéro de version installée : ne plante pas."""
        mock_get.return_value.json.return_value = {"tag_name": "v3.0.0"}
        mock_get.return_value.raise_for_status = MagicMock()

        items = push_version_notification([])
        self.assertEqual(items, [])


@override_settings(
    INFORMATION_URL=INFORMATION_URL,
    LATEST_RELEASE_URL=LATEST_RELEASE_URL,
)
class TestGetAllNotifications(TestCase):
    def setUp(self):
        cache.clear()

    def _mock_response(self, mock_get, items):
        """Helper : simule une réponse JSON avec une liste de notifications."""
        mock_get.return_value.json.return_value = {"items": items}
        mock_get.return_value.raise_for_status = MagicMock()

    def _valid_item(self, **kwargs):
        """Retourne une notification affichable de base, qu'on peut surcharger."""
        item = {
            "type": "info",
            "title": "Notification de test",
            "description": "Description de test",
            "date": date.today().isoformat(),
        }
        item.update(kwargs)
        return item

    # --- URL ---

    @patch("dashboard.utils.requests.get")
    def test_uses_information_url(self, mock_get):
        self._mock_response(mock_get, [])

        get_all_notifications()

        called_urls = [call.args[0] for call in mock_get.call_args_list]
        self.assertIn(settings.INFORMATION_URL, called_urls)

    # --- Erreurs réseau ---

    @patch("dashboard.utils.requests.get")
    def test_empty_if_github_unavailable(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")

        items = get_all_notifications()
        self.assertEqual(items, [])

    @patch("dashboard.utils.requests.get")
    def test_empty_if_bad_url(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_get.return_value = mock_response

        items = get_all_notifications()
        json_items = [i for i in items if "date" in i]
        self.assertEqual(json_items, [])

    # --- Cache ---

    @patch("dashboard.utils.requests.get")
    def test_second_call_uses_cache(self, mock_get):
        self._mock_response(mock_get, [])

        get_all_notifications()
        get_all_notifications()

        self.assertEqual(mock_get.call_count, 2)

    @patch("dashboard.utils.requests.get")
    def test_item_not_displayed_if_no_date(self, mock_get):
        item = self._valid_item()
        del item["date"]
        self._mock_response(mock_get, [item])

        items = get_all_notifications()
        titles = [i["title"] for i in items]
        self.assertNotIn("Notification de test", titles)

    @patch("dashboard.utils.requests.get")
    def test_item_not_displayed_if_only_type(self, mock_get):
        self._mock_response(mock_get, [{"type": "info"}])

        items = get_all_notifications()
        self.assertEqual(items, [])

    # --- Type ---

    @patch("dashboard.utils.requests.get")
    def test_item_not_displayed_if_bad_type(self, mock_get):
        self._mock_response(mock_get, [self._valid_item(type="badtype")])

        items = get_all_notifications()
        titles = [i["title"] for i in items]
        self.assertNotIn("Notification de test", titles)

    @patch("dashboard.utils.requests.get")
    def test_item_not_displayed_if_date_in_future(self, mock_get):
        future_date = (date.today() + timedelta(days=5)).isoformat()
        self._mock_response(mock_get, [self._valid_item(date=future_date)])

        items = get_all_notifications()
        titles = [i["title"] for i in items]
        self.assertNotIn("Notification de test", titles)

    @patch("dashboard.utils.requests.get")
    def test_item_displayed_if_date_is_today(self, mock_get):
        self._mock_response(mock_get, [self._valid_item()])

        items = get_all_notifications()
        titles = [i["title"] for i in items]
        self.assertIn("Notification de test", titles)

    @patch("dashboard.utils.requests.get")
    def test_item_not_displayed_if_date_malformed(self, mock_get):
        self._mock_response(mock_get, [self._valid_item(date="pas-une-date")])

        items = get_all_notifications()
        titles = [i["title"] for i in items]
        self.assertNotIn("Notification de test", titles)

    @patch("dashboard.utils.requests.get")
    def test_item_not_displayed_if_end_date_in_past(self, mock_get):
        past_date = (date.today() - timedelta(days=1)).isoformat()
        self._mock_response(mock_get, [self._valid_item(end_date=past_date)])

        items = get_all_notifications()
        titles = [i["title"] for i in items]
        self.assertNotIn("Notification de test", titles)

    @patch("dashboard.utils.requests.get")
    def test_item_displayed_if_end_date_in_future(self, mock_get):
        future_date = (date.today() + timedelta(days=10)).isoformat()
        self._mock_response(mock_get, [self._valid_item(end_date=future_date)])

        items = get_all_notifications()
        titles = [i["title"] for i in items]
        self.assertIn("Notification de test", titles)

    @patch("dashboard.utils.requests.get")
    def test_item_displayed_if_no_end_date(self, mock_get):
        self._mock_response(mock_get, [self._valid_item()])

        items = get_all_notifications()
        titles = [i["title"] for i in items]
        self.assertIn("Notification de test", titles)

    @patch("dashboard.utils.requests.get")
    def test_item_displayed_if_end_date_empty_string(self, mock_get):
        self._mock_response(mock_get, [self._valid_item(end_date="")])

        items = get_all_notifications()
        titles = [i["title"] for i in items]
        self.assertIn("Notification de test", titles)

    @patch("dashboard.utils.requests.get")
    def test_item_not_displayed_if_end_date_malformed(self, mock_get):
        self._mock_response(mock_get, [self._valid_item(end_date="pas-une-date")])

        items = get_all_notifications()
        titles = [i["title"] for i in items]
        self.assertNotIn("Notification de test", titles)
