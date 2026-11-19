import copy
from datetime import date
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from wagtail.models import Page, Site

from content_manager.models import CatalogIndexPage, ContentPage
from fabrique import betagouv, sync

TODAY = date(2026, 11, 19)


def startup(id, name, phases, incubator="fab-geocommuns", **attrs):
    return {
        "id": id,
        "type": "startup",
        "attributes": {
            "name": name,
            "pitch": attrs.pop("pitch", f"Mission de {name}"),
            "link": attrs.pop("link", f"https://{id}.example.gouv.fr"),
            "repository": "",
            "contact": f"contact@{id}.example.gouv.fr",
            "phases": [{"name": n, "start": s} for n, s in phases],
            "sponsors": ["/organisations/ign"],
            "content_url_encoded_markdown": "%23%23%20Probl%C3%A8me%0A%0AUn%20texte.",
            **attrs,
        },
        "relationships": {"incubator": {"data": {"type": "incubator", "id": incubator}}},
    }


STARTUPS = {
    "data": [
        startup(
            "bat-id",
            "RNB, le Référentiel National des Bâtiments",
            [("investigation", "2021-09-01"), ("consolidation", "2026-01-01")],
        ),
        startup("nouveau.produit", "Nouveau produit", [("investigation", "2026-03-05")]),
        startup("foreg", "FoReg", [("construction", "2024-01-01"), ("abandon", "2026-07-02")]),
        startup("ailleurs", "Produit d'un autre incubateur", [("construction", "2025-01-01")], incubator="autre"),
    ]
}

AUTHORS = [
    {
        "id": "alice.ainsa",
        "fullname": "Alice Ainsa",
        "role": "Développeuse",
        "missions": [
            {"start": "2025-11-03", "end": "2027-08-03", "employer": "IGN", "startups": ["bat-id", "nouveau.produit"]}
        ],
    },
    {
        "id": "nicolas.kokla",
        "fullname": "Nicolas KOKLA",
        "role": "Lead dev",
        "missions": [{"start": "2025-01-01", "end": "2027-01-01", "employer": "", "startups": ["bat-id"]}],
    },
    {
        "id": "ancien.membre",
        "fullname": "Ancien Membre",
        "role": "Dev",
        "missions": [{"start": "2022-01-01", "end": "2024-01-01", "employer": "Malt", "startups": ["bat-id"]}],
    },
    {
        "id": "futur.membre",
        "fullname": "Futur Membre",
        "role": "Dev",
        "missions": [{"start": "2027-01-01", "end": "2028-01-01", "employer": "Malt", "startups": ["bat-id"]}],
    },
]


class ParseTests(TestCase):
    def test_parse_garde_les_produits_actifs_de_l_incubateur(self):
        products, inactive = betagouv.parse(STARTUPS, AUTHORS, "fab-geocommuns", TODAY)
        self.assertEqual([p.id for p in products], ["nouveau.produit", "bat-id"])  # tri par phase
        self.assertEqual(inactive, {"foreg"})
        rnb = products[1]
        self.assertEqual(rnb.phase, "consolidation")
        self.assertEqual(rnb.short_name, "RNB")
        self.assertEqual(rnb.sponsors, ["IGN"])
        self.assertEqual(rnb.markdown, "## Problème\n\nUn texte.")
        self.assertEqual([m.fullname for m in rnb.members], ["Alice Ainsa", "Nicolas Kokla"])

    def test_normalize_name(self):
        self.assertEqual(betagouv.normalize_name("VINCENT SAGNIEZ"), "Vincent Sagniez")
        self.assertEqual(betagouv.normalize_name("Thomas DOS ANJOS"), "Thomas Dos Anjos")
        self.assertEqual(betagouv.normalize_name("Jean-Luc Acquitter"), "Jean-Luc Acquitter")


class SyncTests(TestCase):
    def setUp(self):
        self.root = Site.objects.get(is_default_site=True).root_page
        self.team = ContentPage(
            title="L'équipe",
            slug="equipe",
            body=[{"type": "paragraph", "id": "manuel", "value": "<p>Texte saisi à la main</p>"}],
        )
        self.root.add_child(instance=self.team)
        self.team.save_revision().publish()

    def run_sync(self, startups=STARTUPS, authors=AUTHORS):
        products, inactive = betagouv.parse(startups, authors, "fab-geocommuns", TODAY)
        return sync.run(products, inactive, "produits", "equipe")

    def product_page(self, product_id):
        return ContentPage.objects.get(source_url=f"https://beta.gouv.fr/startups/{product_id}.html")

    def test_premiere_synchro_cree_les_pages(self):
        report = self.run_sync()
        index = CatalogIndexPage.objects.get(slug="produits")
        self.assertTrue(index.live)
        self.assertEqual(
            report.created,
            ["Page Les produits de la Fabrique", "Nouveau produit", "RNB, le Référentiel National des Bâtiments"],
        )

        rnb = self.product_page("bat-id")
        self.assertTrue(rnb.live)
        self.assertEqual(rnb.get_parent().id, index.id)
        self.assertEqual(rnb.slug, "bat-id")
        self.assertEqual([t.name for t in rnb.tags.all()], ["En consolidation"])
        ids = [b["id"] for b in rnb.body.raw_data]
        self.assertEqual(
            ids,
            [
                "betagouv-phase",
                "betagouv-mission",
                "presentation",
                "betagouv-liens",
                "betagouv-equipe-titre",
                "betagouv-equipe",
            ],
        )
        self.assertEqual(self.product_page("nouveau.produit").slug, "nouveau-produit")
        # Pas de présentation rédigée pour ce produit : on reprend le texte de la fiche beta.gouv.
        self.assertEqual(self.product_page("nouveau.produit").body.raw_data[2]["type"], "markdown")

        team = Page.objects.get(id=self.team.id).specific
        team_ids = [b["id"] for b in team.body.raw_data]
        self.assertEqual(team_ids, ["manuel", "betagouv-equipes-titre", "betagouv-equipes"])
        cards = team.body.raw_data[2]["value"]["items"]
        self.assertEqual([c["value"]["name"] for c in cards], ["Alice Ainsa", "Nicolas Kokla"])
        alice_tags = cards[0]["value"]["tags"]
        self.assertEqual(
            [t["value"]["link"]["page"] for t in alice_tags], [self.product_page("nouveau.produit").id, rnb.id]
        )

    def test_deuxieme_synchro_sans_changement_ne_cree_pas_de_revision(self):
        self.run_sync()
        rnb = self.product_page("bat-id")
        revisions = rnb.revisions.count()
        report = self.run_sync()
        self.assertEqual(report.created, [])
        self.assertEqual(report.updated, [])
        self.assertEqual(self.product_page("bat-id").revisions.count(), revisions)

    def test_les_modifications_manuelles_sont_conservees(self):
        self.run_sync()
        rnb = self.product_page("bat-id")
        body = list(rnb.body.raw_data)
        body[2]["value"] = "<p>Présentation réécrite par un éditeur</p>"
        body.insert(0, {"type": "paragraph", "id": "ajout", "value": "<p>Bloc ajouté en tête</p>"})
        rnb.body = body
        rnb.save_revision().publish()

        startups = copy.deepcopy(STARTUPS)
        startups["data"][0]["attributes"]["pitch"] = "Nouvelle mission"
        report = self.run_sync(startups)

        rnb = self.product_page("bat-id")
        self.assertIn("RNB, le Référentiel National des Bâtiments", report.updated)
        raw = list(rnb.body.raw_data)
        self.assertEqual(raw[0]["value"], "<p>Bloc ajouté en tête</p>")
        self.assertEqual(raw[3]["value"], "<p>Présentation réécrite par un éditeur</p>")
        self.assertIn("Nouvelle mission", raw[2]["value"])
        self.assertEqual(rnb.search_description, "Nouvelle mission")

    def test_produit_abandonne_depublie(self):
        self.run_sync()
        startups = copy.deepcopy(STARTUPS)
        startups["data"][1]["attributes"]["phases"].append({"name": "abandon-investigation", "start": "2026-11-01"})
        report = self.run_sync(startups)
        self.assertEqual(report.unpublished, ["Nouveau produit"])
        self.assertFalse(self.product_page("nouveau.produit").live)

    def test_membre_parti_retire_de_l_equipe(self):
        self.run_sync()
        authors = copy.deepcopy(AUTHORS)
        authors[1]["missions"][0]["end"] = "2026-11-01"
        self.run_sync(authors=authors)
        rnb = self.product_page("bat-id")
        cards = next(b for b in rnb.body.raw_data if b["id"] == "betagouv-equipe")["value"]["items"]
        self.assertEqual([c["value"]["name"] for c in cards], ["Alice Ainsa"])

    def test_brouillon_en_cours_non_modifie(self):
        self.run_sync()
        rnb = self.product_page("bat-id")
        rnb.title = "Titre en cours de rédaction"
        rnb.save_revision()  # brouillon non publié
        startups = copy.deepcopy(STARTUPS)
        startups["data"][0]["attributes"]["pitch"] = "Nouvelle mission"
        report = self.run_sync(startups)
        self.assertEqual(report.skipped_drafts, ["RNB, le Référentiel National des Bâtiments"])
        self.assertNotEqual(self.product_page("bat-id").search_description, "Nouvelle mission")

    def test_les_pages_s_affichent(self):
        self.run_sync()
        for url in ["/produits/", "/produits/bat-id/", "/equipe/"]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
        html = self.client.get("/equipe/").content.decode()
        self.assertIn("Nicolas Kokla", html)
        self.assertIn("Lead dev</p>", html)  # pas de tiret quand l'employeur est vide
        self.assertIn("En consolidation", self.client.get("/produits/").content.decode())


class CommandTests(TestCase):
    def test_api_vide_ne_depublie_rien(self):
        with mock.patch.object(betagouv, "load", return_value=([], set())), mock.patch.object(sync, "run") as run:
            call_command("sync_betagouv", stdout=mock.MagicMock(), stderr=mock.MagicMock())
        run.assert_not_called()

    def test_dry_run_n_enregistre_rien(self):
        products, inactive = betagouv.parse(STARTUPS, AUTHORS, "fab-geocommuns", TODAY)
        with mock.patch.object(betagouv, "load", return_value=(products, inactive)):
            call_command("sync_betagouv", "--dry-run", stdout=mock.MagicMock())
        self.assertFalse(CatalogIndexPage.objects.filter(slug="produits").exists())
