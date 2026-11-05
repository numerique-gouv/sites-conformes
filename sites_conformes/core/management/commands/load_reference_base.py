import json
from io import StringIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.migrations.loader import MigrationLoader
from wagtail.images import get_image_model
from wagtail.models import Collection, Page, Site

from sites_conformes.core.management.commands.export_reference_base import FIXTURES_DIR
from sites_conformes.core.services.demo_sites import (
    SITE_KEYS,
    DemoSitesError,
    check_empty_database,
    create_demo_users,
)

Image = get_image_model()


class Command(BaseCommand):
    help = """
    Loads the reference bases of one or several demo sites, exported by export_reference_base,
    into an empty database, with their images. Development only: requires DEBUG.
    """

    def add_arguments(self, parser):
        parser.add_argument("sites", nargs="*", choices=SITE_KEYS, help="Sites to load (default: a)")
        parser.add_argument("--skip-migrate", action="store_true", help="The database is already migrated")

    def handle(self, *args, **kwargs):
        if not settings.DEBUG:
            raise CommandError("Cette commande crée des comptes avec un mot de passe connu : elle exige DEBUG=True.")

        site_keys = sorted(set(kwargs["sites"] or ["a"]))
        manifests = {}
        for site_key in site_keys:
            with open(FIXTURES_DIR / f"site-{site_key}.manifest.json", encoding="utf-8") as manifest_file:
                manifests[site_key] = json.load(manifest_file)
            self.check_models_match(manifests[site_key])

        if not kwargs["skip_migrate"]:
            call_command("migrate", verbosity=0)

        try:
            check_empty_database()
        except DemoSitesError as e:
            raise CommandError(str(e))

        with transaction.atomic():
            # The fixtures contain the pages and the sites that replace the initial Wagtail page and site
            Page.objects.filter(depth=2).delete()
            for site_key in site_keys:
                # Shared objects are in each fixture, and identical
                call_command("loaddata", str(FIXTURES_DIR / f"site-{site_key}.json"), verbosity=0)

            # The root page and collection come from a database with both sites: fix their number of children
            Page.fix_tree()
            Collection.fix_tree()

            # A site loaded alone becomes the default site, as on a monosite instance
            if not Site.objects.filter(is_default_site=True).exists():
                Site.objects.filter(pk=Site.objects.order_by("pk").first().pk).update(is_default_site=True)

            # The fixtures contain a fixed port: use the one of this instance.
            # save() rather than update(), so that Wagtail clears its cache of the site root paths
            port = int(settings.HOST_PORT or 80)
            for site in Site.objects.all():
                site.port = port
                site.save()

            # Accounts that belong to several sites are not in the fixtures
            if len(site_keys) > 1:
                create_demo_users(site_keys, only_cross_site=True)

            # The reference index is not in the fixtures: without it, the admin shows every image as unused
            call_command("rebuild_references_index", stdout=StringIO())

            image_sources = {}
            for manifest in manifests.values():
                image_sources.update(manifest["images"])
            self.restore_images(image_sources)

        self.stdout.write(self.style.SUCCESS(f"Base de référence chargée : site(s) {', '.join(site_keys)}."))

    def check_models_match(self, manifest: dict) -> None:
        """
        loaddata uses the current models: they must be those the fixture was exported with.
        """
        current = dict(MigrationLoader(None, ignore_no_migrations=True).graph.leaf_nodes())
        # Apps installed on one side only (such as db_storage) have no data in the fixture
        changed = sorted(
            app_label
            for app_label in current.keys() & manifest["migrations"].keys()
            if current[app_label] != manifest["migrations"][app_label]
        )
        if changed:
            raise CommandError(
                f"Les migrations du code ne correspondent pas à la base de référence ({', '.join(changed)}). "
                f"Chargez-la depuis le commit {manifest['commit']}, puis revenez sur votre branche "
                "et lancez « migrate »."
            )

    def restore_images(self, image_sources: dict) -> None:
        for image in Image.objects.all():
            source = image_sources.get(image.file.name)
            # Pictograms and illustrations come from the static files, collected by "collectstatic"
            if not source or not (settings.BASE_DIR / source).is_file():
                self.stdout.write(self.style.WARNING(f"Fichier source introuvable pour l'image {image.file.name}"))
                continue

            # If the name is already taken, the storage adds a suffix: it must still fit in the field
            with open(settings.BASE_DIR / source, "rb") as source_file:
                stored_name = default_storage.save(
                    image.file.name, ContentFile(source_file.read()), max_length=image.file.field.max_length
                )

            if stored_name != image.file.name:
                image.file.name = stored_name
                image.save(update_fields=["file"])
