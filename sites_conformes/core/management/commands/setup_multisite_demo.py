from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from sites_conformes.core.services.demo_sites import DEFAULT_PASSWORD, SITE_KEYS, DemoSitesError, create_demo_sites


class Command(BaseCommand):
    help = """
    Creates two fictional demo sites, with their groups, workflows and accounts, to work on the multisite features.
    Development only: requires DEBUG and an empty database.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--monosite",
            nargs="?",
            const="a",
            choices=SITE_KEYS,
            help="Only create one site: A (default) or B",
        )
        parser.add_argument("--without-media", action="store_true", help="Do not import the images")
        parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Password of all the demo accounts")

    def handle(self, *args, **kwargs):
        if not settings.DEBUG:
            raise CommandError("Cette commande crée des comptes avec un mot de passe connu : elle exige DEBUG=True.")

        try:
            demo = create_demo_sites(
                site_keys=(kwargs["monosite"],) if kwargs["monosite"] else SITE_KEYS,
                with_media=not kwargs["without_media"],
                password=kwargs["password"],
            )
        except DemoSitesError as e:
            raise CommandError(str(e))

        self.stdout.write(self.style.SUCCESS("Sites de démo créés :"))
        for site in demo.sites.values():
            self.stdout.write(f"  - {site.site_name} : {site.root_url}/ et {site.root_url}/en/")

        self.stdout.write(self.style.SUCCESS(f"Comptes (mot de passe « {demo.password} ») :"))
        for username, user in demo.users.items():
            groups = ", ".join(user.groups.values_list("name", flat=True)) or "superadmin"
            self.stdout.write(f"  - {username} : {groups}")
