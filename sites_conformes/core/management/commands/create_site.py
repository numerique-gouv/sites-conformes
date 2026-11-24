from django.core.management.base import BaseCommand, CommandError

from sites_conformes.core.services.sites import SiteCreationError, create_site


class Command(BaseCommand):
    help = """
    Creates a site with its home page, image collection, groups, workflow, menus and configuration.
    Running it again with the same hostname and port completes the site, without duplicates.
    """

    def add_arguments(self, parser):
        parser.add_argument("--hostname", required=True, help="Hostname of the site, without protocol nor port")
        parser.add_argument("--name", required=True, help="Name of the site, also used for its groups and collection")
        parser.add_argument("--port", type=int, help="Port of the site. Defaults to HOST_PORT, or 80.")
        parser.add_argument(
            "--locales",
            help="Comma-separated languages of the site, the first one being the language of its home page "
            "(for instance: fr,en). Defaults to the default language.",
        )
        parser.add_argument(
            "--with-starter-pages",
            action="store_true",
            help="Also create the legal notice, accessibility and contact pages",
        )

    def handle(self, *args, **kwargs):
        language_codes = None
        if kwargs["locales"]:
            language_codes = [code.strip() for code in kwargs["locales"].split(",") if code.strip()]

        try:
            setup = create_site(
                hostname=kwargs["hostname"],
                name=kwargs["name"],
                port=kwargs["port"],
                language_codes=language_codes,
                with_starter_pages=kwargs["with_starter_pages"],
                stdout=self.stdout if kwargs["verbosity"] > 1 else None,
            )
        except SiteCreationError as e:
            raise CommandError(str(e))

        site = setup.site
        if setup.created:
            self.stdout.write(self.style.SUCCESS(f"Site « {site.site_name} » créé : {site.root_url}"))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Site « {site.site_name} » déjà existant, complété : {site.root_url}")
            )

        self.stdout.write("Pages d’accueil :")
        for home_page in setup.home_pages:
            self.stdout.write(f"  - {home_page.locale.language_code} : {home_page.title} ({home_page.get_full_url()})")
        self.stdout.write(f"Collection : {setup.collection.name}")
        self.stdout.write("Groupes :")
        for group in setup.groups.values():
            self.stdout.write(f"  - {group.name}")
        self.stdout.write(f"Workflow : {setup.workflow.name}")

        for warning in setup.warnings:
            self.stdout.write(self.style.WARNING(f"Attention : {warning}"))

        # Each process of the application keeps the root pages of the sites in its own cache for an hour:
        # the running ones don't see the changes made by this command.
        self.stdout.write(
            self.style.WARNING("À faire : redémarrez l’application pour qu’elle prenne en compte ce site.")
        )
