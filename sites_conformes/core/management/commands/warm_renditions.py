from urllib.parse import urlsplit

from django.core.management.base import BaseCommand
from django.test import Client, override_settings
from wagtail.models import Page


class Command(BaseCommand):
    help = "Render each live page once so its image renditions exist before visitors ask for them"

    # The pages are rendered in this process only, for the hostnames of the Wagtail sites
    @override_settings(ALLOWED_HOSTS=["*"])
    def handle(self, *args, **options):
        # Listing pages after the first (?page=N) and routable sub-pages stay cold,
        # their renditions are generated on the first visit
        client = Client(raise_request_exception=False)
        rendered = errors = 0
        for page in Page.objects.live().public().exclude(depth=1).iterator():
            url = urlsplit(page.full_url or "")
            if not url.netloc:
                continue
            response = client.get(url.path, headers={"host": url.netloc}, secure=url.scheme == "https", follow=True)
            if response.status_code == 200:
                rendered += 1
            else:
                errors += 1
                self.stderr.write(f"{response.status_code} {page.full_url}")

        self.stdout.write(f"Image renditions warmed: {rendered} pages rendered, {errors} errors")
