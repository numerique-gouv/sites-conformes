import requests
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from sites_conformes.proconnect.models import WhitelistedEmailDomain


class Command(BaseCommand):
    help = """
    Import the allowed domain whitelist for ProConnect from the Suite Numérique API.
    """

    def handle(self, *args, **kwargs):
        api_endpoint = "https://domaines-lasuite.numerique.gouv.fr/v1/domains"
        api_key = settings.LASUITE_DOMAINE_API_KEY
        if not api_key:
            raise ValueError("The LASUITE_DOMAINE_API_KEY environment variable must be set.")

        headers = {"Authorization": f"Bearer {api_key}"}
        result = requests.get(api_endpoint, headers=headers)

        data = result.json()
        if data.get("status", "") != "success":
            raise ValueError("The API call failed.")

        domains = []
        items = set(data.get("items", []))
        for item in items:
            exists = WhitelistedEmailDomain.objects.filter(domain=item).count()
            if not exists:
                domains.append(WhitelistedEmailDomain(domain=item))

        if len(domains):
            self.stdout.write(f"{len(domains)} domains will be imported.")
            WhitelistedEmailDomain.objects.bulk_create(domains)
            call_command("update_index")
            self.stdout.write(self.style.SUCCESS("Import complete."))
        else:
            self.stdout.write(self.style.SUCCESS("No new domain to import."))
