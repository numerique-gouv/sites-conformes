import importlib
from datetime import datetime, timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from wagtail.models import Page, Site
from wagtailmenus.models import MainMenu, MainMenuItem

from blog.models import BlogEntryPage, BlogIndexPage
from content_manager.models import ContentPage
from events.models import EventEntryPage, EventsIndexPage
from fabrique import accueil
from fabrique.models import EtiquettesEvenement, ProduitsIndexPage

# Reconstitution de la page d'accueil du site, dans l'ordre des sections et avec les textes en ligne.
CORPS = [
    {
        "type": "multicolumns",
        "id": "intro",
        "value": {
            "title": "",
            "heading_tag": "h2",
            "columns": [
                {
                    "type": "text",
                    "id": "intro-texte",
                    "value": "<h1>La Fabrique de la donnée territoriale</h1>"
                    "<p>Un espace de coopération et d’innovation publique, opéré par l’IGN.</p>",
                }
            ],
        },
    },
    {"type": "paragraph", "id": "pourquoi", "value": "<h2>Pourquoi une Fabrique de la donnée territoriale ?</h2>"},
    {
        "type": "paragraph",
        "id": "projets",
        "value": "<h2>Les projets de la Fabrique</h2><p>BAN, RNB, Panoramax.</p>",
    },
    {
        "type": "callout",
        "id": "encart",
        "value": {
            "title": "🚀 Projets sélectionnés par le comité des partenaires",
            "heading_tag": "h3",
            "icon_class": "",
            "text": "<p>Le 3e comité des partenaires a engagé le lancement de 3 nouveaux chantiers :</p>"
            "<ul><li>Données de mobilité</li><li>Refuges climatiques</li><li>Mes Données territoriales</li></ul>"
            '<p>Ces sujets vous intéressent : <a href="mailto:fabrique@ign.fr">📧 Contactez-nous</a></p>',
            "color": "",
        },
    },
    {"type": "paragraph", "id": "comment", "value": "<h2>Comment ça marche ?</h2><p>Quatre étapes.</p>"},
    {
        "type": "paragraph",
        "id": "gouvernance",
        "value": "<h3>Collectif vigie</h3>"
        "<p>Un collectif constitué de collaborateurs issus de chaque organisation partenaire se réunit "
        "régulièrement.</p><p>Il prépare les comités.</p>"
        "<h3>Comité des partenaires</h3>"
        "<p>Le comité des partenaires rassemble les responsables de chaque organisation partenaire.</p>"
        "<h3>Comités d’investissement</h3>"
        "<p>Chaque projet incubé à la Fabrique organise tous les six mois un comité d’investissement.</p>",
    },
    {"type": "paragraph", "id": "rejoindre", "value": "<h2>Rejoindre la démarche</h2>"},
]


class AccueilTest(TestCase):
    def setUp(self):
        self.site = Site.objects.get(is_default_site=True)
        racine = Page.objects.get(depth=1)
        self.accueil = ContentPage(title="Accueil", slug="accueil-fabrique", body=CORPS)
        racine.add_child(instance=self.accueil)
        self.accueil.save_revision().publish()
        self.site.root_page = self.accueil
        self.site.save()

        self.produits = self.ajouter(ProduitsIndexPage(title="Les produits de la Fabrique", slug="produits"))
        self.partenaires = self.ajouter(ContentPage(title="Partenaires", slug="partenaires"))
        self.equipe = self.ajouter(ContentPage(title="L'équipe", slug="equipe"))
        self.actualites = self.ajouter(BlogIndexPage(title="Actualités", slug="les-actualites-de-la-fabrique"))
        self.agenda = self.ajouter(EventsIndexPage(title="Agenda", slug="agenda", filter_by_tag=True))

        self.compte_rendu = self.ajouter(
            BlogEntryPage(title="CR 3e comité des partenaires 01/10/2026", slug="cr-3e", date=timezone.now()),
            self.actualites,
        )
        debut = timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=2), datetime.min.time()))
        self.vigie = self.ajouter(
            EventEntryPage(
                title="Collectif vigie, novembre",
                slug="collectif-vigie-novembre",
                date=timezone.now(),
                event_date_start=debut + timedelta(hours=16),
                event_date_end=debut + timedelta(hours=17, minutes=30),
            ),
            self.agenda,
        )
        self.vigie.tags.add("Collectif vigie", "Fabrique de la donnée territoriale")
        self.vigie.save_revision().publish()
        EtiquettesEvenement.objects.create(
            page=self.vigie, type="Collectif vigie", equipes=["Fabrique de la donnée territoriale"]
        )
        self.comite = self.ajouter(
            EventEntryPage(
                title="Comité d'investissement RNB",
                slug="comite-dinvestissement-rnb",
                date=timezone.now(),
                event_date_start=debut + timedelta(days=1, hours=15),
                event_date_end=debut + timedelta(days=1, hours=16),
            ),
            self.agenda,
        )
        self.comite.tags.add("Comité d'investissement", "RNB")
        self.comite.save_revision().publish()

    def ajouter(self, page, parent=None):
        (parent or self.accueil).add_child(instance=page)
        page.save_revision().publish()
        return page

    def brouillon(self):
        return Page.objects.get(id=self.accueil.id).specific.get_latest_revision_as_object()

    def test_brouillon_par_defaut(self):
        rapport = accueil.run()
        self.assertEqual(rapport.ignores, [])
        page = Page.objects.get(id=self.accueil.id).specific
        self.assertTrue(page.has_unpublished_changes)
        # La version en ligne ne bouge pas.
        self.assertEqual([b.id for b in page.body], [b["id"] for b in CORPS])

        ids = [b.id for b in self.brouillon().body]
        self.assertEqual(
            ids,
            [
                "intro",
                "accueil-boutons",
                "pourquoi",
                "projets",
                "encart",
                "accueil-agenda",
                "accueil-actualites",
                "comment",
                "gouvernance",
                "rejoindre",
            ],
        )

    def test_boutons_apres_introduction(self):
        accueil.run()
        boutons = next(b for b in self.brouillon().body if b.id == "accueil-boutons").value["buttons"]
        self.assertEqual(
            [(b.value["text"], b.value["page"].id, b.value["button_type"]) for b in boutons],
            [
                ("Découvrir nos produits", self.produits.id, "fr-btn"),
                ("Voir l'agenda", self.agenda.id, "fr-btn fr-btn--secondary"),
            ],
        )

    def test_boutons_dans_l_en_tete_si_la_page_en_a_un(self):
        self.accueil.header_color_class = "blue-france"
        self.accueil.header_with_title = True
        self.accueil.save_revision().publish()
        accueil.run()
        page = self.brouillon()
        self.assertNotIn("accueil-boutons", [b.id for b in page.body])
        boutons = page.header_cta_buttons[0].value
        self.assertEqual([b.value["text"] for b in boutons], ["Découvrir nos produits", "Voir l'agenda"])

    def test_liens_encart_et_gouvernance(self):
        accueil.run()
        corps = {b.id: b for b in self.brouillon().body}
        encart = corps["encart"].value["text"].source
        lien_cr = (
            f'<p><a linktype="page" id="{self.compte_rendu.id}">Lire le compte rendu du comité des partenaires</a></p>'
        )
        self.assertIn(lien_cr + "<p>Ces sujets vous intéressent", encart)

        gouvernance = corps["gouvernance"].value.source
        vigie = '<p><a href="/agenda/?tag=collectif-vigie">Les prochains collectifs vigie dans l\'agenda</a></p>'
        # Le lien va à la fin de la sous-section, avant le titre suivant.
        self.assertIn("Il prépare les comités.</p>" + vigie + "<h3>Comité des partenaires", gouvernance)
        self.assertIn(
            f'partenaire.</p><p><a linktype="page" id="{self.compte_rendu.id}">Lire le dernier compte rendu</a></p>'
            "<h3>Comités",
            gouvernance,
        )
        self.assertTrue(
            gouvernance.endswith(
                "?tag=comit%C3%A9-dinvestissement\">Les prochains comités d'investissement dans l'agenda</a></p>"
            )
        )

    def test_relance_sans_doublon(self):
        accueil.run(publier=True)
        rapport = accueil.run(publier=True)
        self.assertIn("Page d'accueil : rien à changer", rapport.faits)
        corps = Page.objects.get(id=self.accueil.id).specific.body
        self.assertEqual(sum(1 for b in corps if b.id == "accueil-agenda"), 1)
        self.assertEqual(corps[4].value["text"].source.count("Lire le compte rendu"), 1)

    def test_refuse_un_brouillon_en_cours(self):
        self.accueil.title = "Accueil modifié"
        self.accueil.save_revision()
        with self.assertRaises(ValueError):
            accueil.run()

    def test_section_absente_signalee(self):
        self.accueil.body = [b for b in CORPS if b["id"] not in ("comment", "gouvernance")]
        self.accueil.save_revision().publish()
        rapport = accueil.run()
        self.assertTrue(any("Comment ça marche" in m for m in rapport.ignores))
        self.assertEqual([b.id for b in self.brouillon().body][-2:], ["accueil-agenda", "accueil-actualites"])

    def test_rendu_de_la_page(self):
        accueil.run(publier=True)
        reponse = self.client.get("/")
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn("Prochains rendez-vous", contenu)
        self.assertIn("Collectif vigie, novembre", contenu)
        self.assertIn("16h", contenu)
        self.assertIn("fabrique-tag-type", contenu)
        self.assertIn("/agenda/ical/", contenu)
        self.assertIn("Dernières actualités", contenu)
        self.assertIn("CR 3e comité des partenaires", contenu)
        self.assertIn("Découvrir nos produits", contenu)
        self.assertIn("Publié le", contenu)

    def test_menu(self):
        menu = MainMenu.get_for_site(self.site)
        for i, page in enumerate(
            [self.accueil, self.partenaires, self.equipe, self.produits, self.actualites, self.agenda]
        ):
            MainMenuItem.objects.create(menu=menu, link_page=page, sort_order=i)
        rapport = accueil.run(menu=True)
        self.assertIn(
            "Menu : Accueil · Partenaires · L'équipe · Les produits de la Fabrique · Actualités · Agenda → "
            "Accueil · Les produits de la Fabrique · Agenda · Actualités · Partenaires · L'équipe",
            rapport.faits,
        )
        ordre = [i.link_page_id for i in MainMenuItem.objects.filter(menu=menu).order_by("sort_order")]
        self.assertEqual(
            ordre,
            [
                self.accueil.id,
                self.produits.id,
                self.agenda.id,
                self.actualites.id,
                self.partenaires.id,
                self.equipe.id,
            ],
        )

    def test_commande_simulation(self):
        sortie = StringIO()
        call_command("maj_accueil", "--dry-run", stdout=sortie, stderr=StringIO())
        self.assertIn("[simulation] ✔ Prochains rendez-vous : bloc ajouté", sortie.getvalue())
        self.assertFalse(Page.objects.get(id=self.accueil.id).has_unpublished_changes)

    def test_migration_de_deploiement(self):
        migration = importlib.import_module("fabrique.migrations.0003_maj_accueil")
        migration.maj_accueil(None, None)
        self.assertIn("accueil-agenda", [b.id for b in self.brouillon().body])
        # Relancée sur un brouillon en cours, elle ne fait rien et ne lève pas d'erreur.
        migration.maj_accueil(None, None)
        self.assertTrue(Page.objects.get(id=self.accueil.id).has_unpublished_changes)
