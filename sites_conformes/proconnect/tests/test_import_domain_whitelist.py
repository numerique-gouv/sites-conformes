from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from sites_conformes.proconnect.models import WhitelistedEmailDomain

COMMAND_MODULE = "sites_conformes.proconnect.management.commands.import_domain_whitelist"


@override_settings(LASUITE_DOMAINE_API_KEY="api-key")
class ImportDomainWhitelistTestCase(TestCase):
    def call_command(self):
        out = StringIO()
        call_command("import_domain_whitelist", stdout=out)
        return out.getvalue()

    @override_settings(LASUITE_DOMAINE_API_KEY=None)
    def test_missing_api_key_raises(self):
        with self.assertRaisesMessage(ValueError, "LASUITE_DOMAINE_API_KEY"):
            self.call_command()

    @patch(f"{COMMAND_MODULE}.requests.get")
    def test_api_failure_raises(self, mock_get):
        mock_get.return_value.json.return_value = {"status": "error"}

        with self.assertRaisesMessage(ValueError, "The API call failed."):
            self.call_command()

    @patch(f"{COMMAND_MODULE}.call_command")
    @patch(f"{COMMAND_MODULE}.requests.get")
    def test_new_domains_are_imported(self, mock_get, mock_call_command):
        WhitelistedEmailDomain.objects.create(domain="beta.gouv.fr")
        mock_get.return_value.json.return_value = {
            "status": "success",
            "items": ["beta.gouv.fr", "numerique.gouv.fr", "numerique.gouv.fr", "education.gouv.fr"],
        }

        output = self.call_command()

        self.assertEqual(mock_get.call_args.kwargs["headers"], {"Authorization": "Bearer api-key"})
        self.assertEqual(
            set(WhitelistedEmailDomain.objects.values_list("domain", flat=True)),
            {"beta.gouv.fr", "numerique.gouv.fr", "education.gouv.fr"},
        )
        self.assertIn("2 domains will be imported.", output)
        mock_call_command.assert_called_once_with("update_index")

    @patch(f"{COMMAND_MODULE}.call_command")
    @patch(f"{COMMAND_MODULE}.requests.get")
    def test_nothing_to_import(self, mock_get, mock_call_command):
        WhitelistedEmailDomain.objects.create(domain="beta.gouv.fr")
        mock_get.return_value.json.return_value = {"status": "success", "items": ["beta.gouv.fr"]}

        output = self.call_command()

        self.assertIn("No new domain to import.", output)
        self.assertEqual(WhitelistedEmailDomain.objects.count(), 1)
        mock_call_command.assert_not_called()
