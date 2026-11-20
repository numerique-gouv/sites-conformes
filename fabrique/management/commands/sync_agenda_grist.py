import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fabrique import agenda, calendriers, grist


class Command(BaseCommand):
    help = (
        "Synchronise l'agenda de la Fabrique : importe d'abord les calendriers iCal configurés "
        "(AGENDA_CALENDRIERS) dans le document Grist « Agenda », puis publie sur le site la page Agenda "
        "et une page Événement par événement publié."
    )

    def add_arguments(self, parser):
        parser.add_argument("--grist-url", default=os.getenv("GRIST_BASE_URL", grist.DEFAULT_BASE_URL))
        parser.add_argument("--org", default=os.getenv("GRIST_AGENDA_ORG", grist.DEFAULT_ORG))
        parser.add_argument("--doc", default=os.getenv("GRIST_AGENDA_DOC_ID", grist.DEFAULT_DOC_ID))
        parser.add_argument("--agenda-slug", default=os.getenv("FABRIQUE_AGENDA_SLUG", "agenda"))
        parser.add_argument("--dry-run", action="store_true", help="Affiche ce qui changerait sans rien enregistrer")
        parser.add_argument(
            "--sans-calendriers", action="store_true", help="N'importe pas les calendriers iCal dans le Grist"
        )

    def handle(self, *args, **options):
        api_key = os.getenv("GRIST_API_KEY", "").strip()
        if not api_key:
            raise CommandError("Variable d'environnement GRIST_API_KEY absente : agenda non synchronisé.")

        source = agenda.Source(base_url=options["grist_url"], org=options["org"], doc_id=options["doc"])
        try:
            records = grist.fetch_records(source.base_url, source.doc_id, api_key)
        except RuntimeError as e:
            raise CommandError(str(e)) from e

        if not records and agenda.synced_live_pages(options["agenda_slug"], source):
            # Garde-fou : une table vide (document remplacé, mauvaise clé…) ne doit pas vider l'agenda.
            # Pour retirer des événements du site, décochez « Publié » dans Grist.
            self.stderr.write("Table Evenements vide dans Grist : synchronisation annulée.")
            return

        prefix = "[simulation] " if options["dry_run"] else ""
        if not options["sans_calendriers"]:
            try:
                liste = calendriers.depuis_env(os.getenv("AGENDA_CALENDRIERS"))
            except ValueError as e:
                raise CommandError(str(e)) from e
            resultats = calendriers.importer(
                liste, records, source.base_url, source.doc_id, api_key, ecrire=not options["dry_run"]
            )
            for resultat in resultats:
                (self.stderr if resultat.erreur else self.stdout).write(f"{prefix}Calendrier {resultat.resume()}")
            if not options["dry_run"] and any(r.plan for r in resultats if r.plan is not None):
                try:
                    records = grist.fetch_records(source.base_url, source.doc_id, api_key)
                except RuntimeError as e:
                    raise CommandError(str(e)) from e

        evenements = grist.parse(records)
        self.stdout.write(f"{len(evenements)} événements publiés sur {len(records)} lignes dans Grist.")

        with transaction.atomic():
            try:
                # En simulation, pas d'import d'image : le fichier resterait dans le stockage malgré l'annulation.
                pieces_jointes = (
                    None if options["dry_run"] else grist.PiecesJointes(source.base_url, source.doc_id, api_key)
                )
                report = agenda.run(evenements, options["agenda_slug"], source, pieces_jointes)
            except RuntimeError as e:
                raise CommandError(str(e)) from e
            if options["dry_run"]:
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
