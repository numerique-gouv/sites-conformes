import json
from os.path import isfile

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from sites_conformes.content_manager.models import CmsDsfrConfig
from sites_conformes.content_manager.utils import get_default_site


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        """
        Sets the site hostname, site_name and port,
        and imports contents from the config.json file if present.
        """

        # Set the site hostname and site_name
        if "http://" in settings.HOST_URL or "https://" in settings.HOST_URL:
            raise ValueError("""The HOST_URL environment variable must contain the domain name only,
                without the port or http/https protocol.""")

        site = get_default_site()
        site.hostname = settings.HOST_URL
        site.site_name = settings.WAGTAIL_SITE_NAME

        if settings.HOST_PORT:
            site.port = settings.HOST_PORT

        site.save()

        # Translate the names of the default user groups.
        mods_group = Group.objects.filter(name="Moderators").first()
        if mods_group:
            mods_group.name = "Modérateurs"
            mods_group.save()

        editors_group = Group.objects.filter(name="Editors").first()
        if editors_group:
            editors_group.name = "Éditeurs"
            editors_group.save()

        # Import config.json
        if isfile("config.json"):
            with open("config.json") as config_file:
                config_data = json.load(config_file)

                config_data["site_id"] = site.id

                _config, created = CmsDsfrConfig.objects.get_or_create(id=1, defaults=config_data)
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Config imported for {config_data.get('site_title', '')}"))
                else:
                    self.stdout.write(self.style.SUCCESS("Config already existing, data not imported."))
