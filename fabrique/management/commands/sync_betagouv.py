import os
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from fabrique import betagouv, sync


class Command(BaseCommand):
    help = (
        "Synchronise les produits et les équipes de l'incubateur depuis beta.gouv.fr : "
        "catalogue des produits, une fiche par produit actif, section « Les équipes produits » de la page Équipe."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--incubator", default=os.getenv("BETAGOUV_INCUBATOR", "fab-geocommuns"), help="Identifiant beta.gouv"
        )
        parser.add_argument("--api", default=os.getenv("BETAGOUV_API_BASE", betagouv.DEFAULT_API_BASE))
        parser.add_argument("--products-slug", default=os.getenv("FABRIQUE_PRODUCTS_SLUG", "produits"))
        parser.add_argument("--team-slug", default=os.getenv("FABRIQUE_TEAM_SLUG", "equipe"))
        parser.add_argument("--sans-images", action="store_true", help="Ne pas importer photos et captures d'écran")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche ce qui changerait sans rien enregistrer (et sans importer d'images)",
        )

    def handle(self, *args, **options):
        products, _inactive = betagouv.load(options["api"], options["incubator"], date.today())
        self.stdout.write(f"{len(products)} produits actifs sur beta.gouv.fr pour « {options['incubator']} » :")
        for p in products:
            self.stdout.write(f"  - {p.name} ({p.phase_label}, {len(p.members)} membres)")
        if not products:
            # Garde-fou : une réponse vide de l'API ne doit pas dépublier toutes les fiches.
            self.stderr.write("Aucun produit actif trouvé : synchronisation annulée.")
            return

        sync_options = sync.Options(with_images=not (options["sans_images"] or options["dry_run"]))
        with transaction.atomic():
            report = sync.run(products, options["products_slug"], options["team_slug"], sync_options)
            if options["dry_run"]:
                transaction.set_rollback(True)

        prefix = "[simulation] " if options["dry_run"] else ""
        for label, items in (
            ("créées", report.created),
            ("mises à jour", report.updated),
            ("inchangées", report.unchanged),
            ("dépubliées", report.unpublished),
            ("ignorées (brouillon en cours)", report.skipped_drafts),
        ):
            if items:
                self.stdout.write(f"{prefix}Pages {label} : {', '.join(items)}")
