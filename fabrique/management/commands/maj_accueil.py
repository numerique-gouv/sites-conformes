from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fabrique import accueil


class Command(BaseCommand):
    help = (
        "Complète la page d'accueil avec les pages Produits, Agenda et Actualités : boutons du bandeau, "
        "prochains rendez-vous, dernières actualités, liens de la gouvernance et de l'encart du comité. "
        "Enregistre un brouillon, sauf avec --publier."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--publier", action="store_true", help="Publie directement au lieu d'enregistrer un brouillon"
        )
        parser.add_argument(
            "--menu",
            action="store_true",
            help="Réordonne aussi le menu principal (Produits, Agenda, Actualités après Accueil). Effet immédiat.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Affiche ce qui changerait sans rien enregistrer")

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                rapport = accueil.run(publier=options["publier"], menu=options["menu"], simulation=options["dry_run"])
                if options["dry_run"]:
                    transaction.set_rollback(True)
        except ValueError as e:
            raise CommandError(str(e)) from e

        prefixe = "[simulation] " if options["dry_run"] else ""
        for ligne in rapport.faits:
            self.stdout.write(f"{prefixe}✔ {ligne}")
        for ligne in rapport.ignores:
            self.stderr.write(f"{prefixe}⚠ {ligne}")
