"""Seed the demo annuaire app: a handful of Psychologue snippets and an
AnnuairePage with the map block.

Idempotent: re-running the command does not duplicate rows. Snippets are keyed
by `nom` and the page by `slug`.
"""

from django.core.management.base import BaseCommand
from wagtail.models import Page

from annuaire.models import AnnuairePage, Psychologue

DEMO_PSYCHOLOGUES = [
    {"nom": "Marie Dupont", "ville": "Paris", "lat": 48.856614, "lng": 2.352222},
    {"nom": "Jean Martin", "ville": "Lyon", "lat": 45.764043, "lng": 4.835659},
    {"nom": "Sophie Bernard", "ville": "Marseille", "lat": 43.296482, "lng": 5.369780},
    {"nom": "Pierre Dubois", "ville": "Bordeaux", "lat": 44.837789, "lng": -0.579180},
    {"nom": "Claire Moreau", "ville": "Nantes", "lat": 47.218371, "lng": -1.553621},
    {"nom": "Antoine Laurent", "ville": "Strasbourg", "lat": 48.583148, "lng": 7.747882},
]

PAGE_SLUG = "annuaire"
PAGE_TITLE = "Annuaire des psychologues"


class Command(BaseCommand):
    help = "Seed demo data: Psychologue snippets + an AnnuairePage with the map block."

    def handle(self, *args, **options):
        psy_created, psy_existing = self._seed_psychologues()
        page_status = self._seed_page()

        self.stdout.write(self.style.SUCCESS("Seed terminé."))
        self.stdout.write(f"  Psychologues : {psy_created} créés, {psy_existing} déjà présents.")
        self.stdout.write(f"  AnnuairePage : {page_status}.")

    def _seed_psychologues(self) -> tuple[int, int]:
        created = 0
        existing = 0
        for entry in DEMO_PSYCHOLOGUES:
            _, was_created = Psychologue.objects.get_or_create(
                nom=entry["nom"],
                defaults={
                    "ville": entry["ville"],
                    "latitude": entry["lat"],
                    "longitude": entry["lng"],
                },
            )
            if was_created:
                created += 1
            else:
                existing += 1
        return created, existing

    def _seed_page(self) -> str:
        # If the page already exists (by slug), do nothing.
        if AnnuairePage.objects.filter(slug=PAGE_SLUG).exists():
            return "déjà présente (slug=annuaire)"

        # Place under the site's root page (the default HomePage created by
        # `manage.py migrate` + wagtail's initial data fixture).
        root = Page.objects.filter(depth=2).first()
        if root is None:
            return "ignorée — aucune page racine. Lancez `migrate` avant `seed_annuaire`."

        page = AnnuairePage(
            title=PAGE_TITLE,
            slug=PAGE_SLUG,
            body=[("liste_psychologues", None)],
        )
        root.add_child(instance=page)
        page.save_revision().publish()
        return f"créée et publiée à /{PAGE_SLUG}/"
