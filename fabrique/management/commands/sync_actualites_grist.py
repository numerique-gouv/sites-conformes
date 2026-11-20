import os
from datetime import datetime, timedelta, timezone

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fabrique import actualites, grist, newsletters


class Command(BaseCommand):
    help = (
        "Synchronise les actualités de la Fabrique : importe d'abord les infolettres Brevo des équipes "
        "(NEWSLETTERS_BREVO) dans la table Actus du Grist, puis publie sur le site un article par actu publiée."
    )

    def add_arguments(self, parser):
        parser.add_argument("--grist-url", default=os.getenv("GRIST_BASE_URL", grist.DEFAULT_BASE_URL))
        parser.add_argument("--org", default=os.getenv("GRIST_AGENDA_ORG", grist.DEFAULT_ORG))
        parser.add_argument("--doc", default=os.getenv("GRIST_AGENDA_DOC_ID", grist.DEFAULT_DOC_ID))
        parser.add_argument("--actus-slug", default=os.getenv("FABRIQUE_ACTUS_SLUG", "actualites"))
        parser.add_argument("--dry-run", action="store_true", help="Affiche ce qui changerait sans rien enregistrer")
        parser.add_argument(
            "--sans-newsletters", action="store_true", help="N'importe pas les infolettres Brevo dans le Grist"
        )
        parser.add_argument(
            "--lister",
            action="store_true",
            help="Affiche les campagnes Brevo de chaque compte (gardées ou écartées) sans rien écrire, puis s'arrête",
        )
        parser.add_argument(
            "--jours",
            type=int,
            default=365,
            help="Ancienneté maximale des campagnes Brevo lues (365 jours par défaut)",
        )

    def handle(self, *args, **options):
        api_key = os.getenv("GRIST_API_KEY", "").strip()
        if not api_key:
            raise CommandError("Variable d'environnement GRIST_API_KEY absente : actualités non synchronisées.")

        source = actualites.Source(base_url=options["grist_url"], org=options["org"], doc_id=options["doc"])

        def lire():
            return grist.fetch_records(source.base_url, source.doc_id, api_key, table=grist.TABLE_ACTUS)

        try:
            records = lire()
        except RuntimeError as e:
            raise CommandError(str(e)) from e

        simulation = options["dry_run"] or options["lister"]
        prefix = "[simulation] " if simulation else ""
        if not options["sans_newsletters"]:
            try:
                comptes = newsletters.depuis_env(os.getenv("NEWSLETTERS_BREVO"))
            except ValueError as e:
                raise CommandError(str(e)) from e
            depuis = datetime.now(timezone.utc) - timedelta(days=options["jours"])
            resultats = newsletters.importer(
                comptes, records, source.base_url, source.doc_id, api_key, os.environ, depuis, ecrire=not simulation
            )
            for resultat in resultats:
                (self.stderr if resultat.erreur else self.stdout).write(f"{prefix}Brevo {resultat.resume()}")
                if options["lister"]:
                    self.stdout.write(f"  Filtre : {resultat.compte.filtre}")
                    for ligne in newsletters.lister(resultat):
                        self.stdout.write(ligne)
            if options["lister"]:
                return
            if not simulation and any(r.plan for r in resultats if r.plan is not None):
                try:
                    records = lire()
                except RuntimeError as e:
                    raise CommandError(str(e)) from e

        if not records and actualites.synced_live_pages(source):
            # Garde-fou : une table vide (document remplacé, mauvaise clé…) ne doit pas vider les actualités.
            # Pour retirer une actu du site, décochez « Publié » dans Grist.
            self.stderr.write("Table Actus vide dans Grist : synchronisation annulée.")
            return

        actus = actualites.parse(records)
        self.stdout.write(f"{len(actus)} actus publiées sur {len(records)} lignes dans Grist.")

        with transaction.atomic():
            try:
                # En simulation, pas d'import d'image : le fichier resterait dans le stockage malgré l'annulation.
                pieces_jointes = None if simulation else grist.PiecesJointes(source.base_url, source.doc_id, api_key)
                report = actualites.run(actus, options["actus_slug"], source, pieces_jointes)
            except RuntimeError as e:
                raise CommandError(str(e)) from e
            if simulation:
                transaction.set_rollback(True)

        for label, items in (
            ("créées", report.created),
            ("mises à jour", report.updated),
            ("inchangées", report.unchanged),
            ("dépubliées", report.unpublished),
            ("ignorées (brouillon en cours)", report.skipped_drafts),
        ):
            if items:
                self.stdout.write(f"{prefix}Pages {label} : {', '.join(items)}")
