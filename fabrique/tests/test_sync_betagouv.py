import copy
from datetime import date
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from wagtail.models import Page, Site

from content_manager.models import ContentPage
from fabrique import betagouv, images, sync
from fabrique.models import ImageImportee, ProduitPage, ProduitsIndexPage

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
        "role": "Lead dev BAN &amp; RNB",
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


STARTUP_HTML = """
<img src="https://espace-membre.example/startups/bat-id/shot.jpg?v=2026111916" alt="">
<div class="fr-col-3"><div class="fr-card fr-card--grey"><div class="fr-card__body">
  <h3 class="fr-card__title"><a href="https://exemple.fr">Nicolas KOKLA</a></h3></div>
  <div class="fr-card__header"><img class="lozad avatar-rounded"
    data-src="https://espace-membre.example/members/nicolas.kokla/avatar.jpg"
    src="data:image/gif;base64,R0" alt=""/></div>
</div></div>
<div class="fr-card fr-card--grey"><h3 class="fr-card__title">Alice Ainsa</h3>
  <img class="lozad" data-src="/img/logo-generique-startup-carre-2019.jpg" src="data:image/gif;base64,R0"></div>
<div class="fr-card fr-card--grey"><h3 class="fr-card__title">Félix Veith</h3>
  <img class="lozad" data-src="/img/authors/felix-veith.jpg?v=1" src="data:image/gif;base64,R0"></div>
"""


def png_bytes(color=(0, 0, 145)) -> bytes:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (40, 40), color).save(buffer, format="PNG")
    return buffer.getvalue()


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
        self.assertEqual(rnb.members[1].role, "Lead dev BAN & RNB")  # entités HTML de l'API décodées

    def test_normalize_name(self):
        self.assertEqual(betagouv.normalize_name("VINCENT SAGNIEZ"), "Vincent Sagniez")
        self.assertEqual(betagouv.normalize_name("Thomas DOS ANJOS"), "Thomas Dos Anjos")
        self.assertEqual(betagouv.normalize_name("Jean-Luc Acquitter"), "Jean-Luc Acquitter")

    def test_parse_startup_page(self):
        shot, photos = betagouv.parse_startup_page(STARTUP_HTML)
        self.assertEqual(shot, "https://espace-membre.example/startups/bat-id/shot.jpg")
        self.assertEqual(
            photos,
            {
                "nicolas kokla": "https://espace-membre.example/members/nicolas.kokla/avatar.jpg",
                "felix veith": "https://beta.gouv.fr/img/authors/felix-veith.jpg",
            },
        )


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
        self.downloads = []
        self.image_bytes = {}

    def fake_download(self, url):
        self.downloads.append(url)
        return self.image_bytes.get(url, png_bytes())

    def options(self, pages=None):
        pages = (
            pages
            if pages is not None
            else {
                "bat-id": (
                    "https://espace-membre.example/startups/bat-id/shot.png",
                    {"nicolas kokla": "https://espace-membre.example/members/nicolas.kokla/avatar.png"},
                )
            }
        )
        return sync.Options(
            load_images=lambda product_id: pages.get(product_id, ("", {})),
            import_image=lambda url, title: images.import_image(url, title, downloader=self.fake_download),
        )

    def run_sync(self, startups=STARTUPS, authors=AUTHORS, options=None):
        products, _ = betagouv.parse(startups, authors, "fab-geocommuns", TODAY)
        return sync.run(products, "produits", "equipe", options or self.options())

    def fiche(self, product_id):
        return ProduitPage.objects.get(betagouv_id=product_id)

    def test_premiere_synchro_cree_catalogue_et_fiches(self):
        report = self.run_sync()
        index = ProduitsIndexPage.objects.get(slug="produits")
        self.assertTrue(index.live)
        self.assertEqual(
            report.created,
            ["Page Les produits de la Fabrique", "Nouveau produit", "RNB, le Référentiel National des Bâtiments"],
        )
        rnb = self.fiche("bat-id")
        self.assertTrue(rnb.live)
        self.assertEqual(rnb.get_parent().id, index.id)
        self.assertEqual(rnb.slug, "bat-id")
        self.assertEqual(rnb.phase, "consolidation")
        self.assertEqual(rnb.porteurs, ["IGN"])
        self.assertEqual(rnb.description_betagouv, "## Problème\n\nUn texte.")
        self.assertEqual([m["nom"] for m in rnb.membres], ["Alice Ainsa", "Nicolas Kokla"])
        self.assertIsNotNone(rnb.capture)
        alice, nicolas = rnb.equipe()
        self.assertIsNone(alice["image"])
        self.assertEqual(nicolas["image"].title, "Nicolas Kokla")
        self.assertEqual(self.fiche("nouveau.produit").slug, "nouveau-produit")

        team = Page.objects.get(id=self.team.id).specific
        self.assertEqual(
            [b["id"] for b in team.body.raw_data], ["manuel", "betagouv-equipes-titre", "betagouv-equipes"]
        )
        cards = team.body.raw_data[2]["value"]["items"]
        self.assertEqual([c["value"]["name"] for c in cards], ["Alice Ainsa", "Nicolas Kokla"])
        self.assertEqual(cards[1]["value"]["image"], nicolas["image"].id)
        avatar = ImageImportee.objects.get(url="static:fabrique/avatar-defaut.png").image
        self.assertEqual(cards[0]["value"]["image"], avatar.id)  # Alice : pictogramme de la Fabrique
        alice_tags = cards[0]["value"]["tags"]
        self.assertEqual([t["value"]["link"]["page"] for t in alice_tags], [self.fiche("nouveau.produit").id, rnb.id])

    def test_deuxieme_synchro_sans_changement(self):
        self.run_sync()
        revisions = self.fiche("bat-id").revisions.count()
        images_count = ImageImportee.objects.count()
        report = self.run_sync()
        self.assertEqual(report.created, [])
        self.assertEqual(report.updated, [])
        self.assertEqual(self.fiche("bat-id").revisions.count(), revisions)
        self.assertEqual(ImageImportee.objects.count(), images_count)

    def test_photo_changee_a_la_source_remplacee(self):
        self.run_sync()
        old_id = self.fiche("bat-id").membres[1]["photo"]
        self.image_bytes["https://espace-membre.example/members/nicolas.kokla/avatar.png"] = png_bytes((200, 0, 0))
        report = self.run_sync()
        self.assertIn("RNB, le Référentiel National des Bâtiments", report.updated)
        self.assertNotEqual(self.fiche("bat-id").membres[1]["photo"], old_id)

    def test_page_beta_gouv_inaccessible_garde_les_photos(self):
        self.run_sync()
        before = self.fiche("bat-id")
        options = self.options()
        options.load_images = lambda product_id: None
        self.run_sync(options=options)
        after = self.fiche("bat-id")
        self.assertEqual(after.membres, before.membres)
        self.assertEqual(after.capture_id, before.capture_id)

    def test_corps_de_page_conserve(self):
        self.run_sync()
        rnb = self.fiche("bat-id")
        rnb.body = [{"type": "paragraph", "id": "edito", "value": "<p>Présentation rédigée dans Wagtail</p>"}]
        rnb.save_revision().publish()
        startups = copy.deepcopy(STARTUPS)
        startups["data"][0]["attributes"]["pitch"] = "Nouvelle mission"
        report = self.run_sync(startups)
        rnb = self.fiche("bat-id")
        self.assertIn("RNB, le Référentiel National des Bâtiments", report.updated)
        self.assertEqual(rnb.pitch, "Nouvelle mission")
        self.assertEqual(rnb.search_description, "Nouvelle mission")
        self.assertEqual(list(rnb.body.raw_data)[0]["value"], "<p>Présentation rédigée dans Wagtail</p>")

    def test_blocs_manuels_de_la_page_equipe_conserves(self):
        self.run_sync()
        team = Page.objects.get(id=self.team.id).specific
        body = list(team.body.raw_data)
        body.append({"type": "paragraph", "id": "apres", "value": "<p>Nous rejoindre</p>"})
        team.body = body
        team.save_revision().publish()
        authors = copy.deepcopy(AUTHORS)
        authors[1]["missions"][0]["end"] = "2026-11-01"
        self.run_sync(authors=authors)
        team = Page.objects.get(id=self.team.id).specific
        ids = [b["id"] for b in team.body.raw_data]
        self.assertEqual(ids, ["manuel", "betagouv-equipes-titre", "betagouv-equipes", "apres"])
        cards = team.body.raw_data[2]["value"]["items"]
        self.assertEqual([c["value"]["name"] for c in cards], ["Alice Ainsa"])

    def test_produit_abandonne_depublie(self):
        self.run_sync()
        startups = copy.deepcopy(STARTUPS)
        startups["data"][1]["attributes"]["phases"].append({"name": "abandon-investigation", "start": "2026-11-01"})
        report = self.run_sync(startups)
        self.assertEqual(report.unpublished, ["Nouveau produit"])
        self.assertFalse(self.fiche("nouveau.produit").live)

    def test_actualites_du_produit_sur_la_fiche(self):
        from blog.models import BlogEntryPage, BlogIndexPage, Category

        category = Category.objects.create(
            name="Référentiel national du bâtiment", slug="referentiel-national-du-batiment"
        )
        blog = BlogIndexPage(title="Actualités", slug="actualites")
        self.root.add_child(instance=blog)
        for day in (1, 2, 3, 4):
            entry = BlogEntryPage(title=f"Actus du RNB {day}", slug=f"actus-{day}", date=f"2026-0{day}-01T10:00Z")
            blog.add_child(instance=entry)
            entry.blog_categories.add(category)
            entry.save_revision().publish()

        self.run_sync()
        rnb = self.fiche("bat-id")
        self.assertEqual(rnb.categorie_actualites, category)
        self.assertIsNone(self.fiche("nouveau.produit").categorie_actualites)
        actus = rnb.actualites()
        self.assertEqual([e.title for e in actus["entrees"]], ["Actus du RNB 4", "Actus du RNB 3", "Actus du RNB 2"])
        self.assertEqual(actus["tout"], "/actualites/?category=referentiel-national-du-batiment")
        html = self.client.get("/produits/bat-id/").content.decode()
        self.assertIn("Toutes les actualités du produit", html)
        self.assertIn("Actus du RNB 4", html)

        # Choix d'un éditeur respecté aux synchros suivantes.
        autre = Category.objects.create(name="Autre", slug="autre")
        rnb.categorie_actualites = autre
        rnb.save_revision().publish()
        self.run_sync()
        self.assertEqual(self.fiche("bat-id").categorie_actualites, autre)

    def test_brouillon_en_cours_non_modifie(self):
        self.run_sync()
        rnb = self.fiche("bat-id")
        rnb.title = "Titre en cours de rédaction"
        rnb.save_revision()
        startups = copy.deepcopy(STARTUPS)
        startups["data"][0]["attributes"]["pitch"] = "Nouvelle mission"
        report = self.run_sync(startups)
        self.assertEqual(report.skipped_drafts, ["RNB, le Référentiel National des Bâtiments"])
        self.assertNotEqual(self.fiche("bat-id").pitch, "Nouvelle mission")

    def test_les_pages_s_affichent(self):
        self.run_sync()
        catalogue = self.client.get("/produits/")
        self.assertEqual(catalogue.status_code, 200)
        html = catalogue.content.decode()
        self.assertIn("En consolidation (1)", html)
        self.assertIn("/produits/bat-id/", html)
        # Les produits les plus avancés d'abord : RNB (consolidation) avant le produit en investigation.
        self.assertLess(html.index("/produits/bat-id/"), html.index("/produits/nouveau-produit/"))
        filtre = self.client.get("/produits/?phase=en-investigation").content.decode()
        self.assertIn("Nouveau produit", filtre)
        self.assertNotIn("/produits/bat-id/", filtre)

        fiche = self.client.get("/produits/bat-id/")
        self.assertEqual(fiche.status_code, 200)
        html = fiche.content.decode()
        self.assertIn("Mission de RNB", html)
        self.assertIn("<h2>Problème</h2>", html)
        self.assertIn("En quelques dates", html)
        self.assertIn("bat-id.example.gouv.fr", html)
        self.assertIn("fabrique/avatar-defaut", html)  # Alice n'a pas de photo : pictogramme de la Fabrique

        equipe = self.client.get("/equipe/").content.decode()
        self.assertIn("Lead dev BAN &amp; RNB</p>", equipe)  # pas de tiret quand l'employeur est vide


class CommandTests(TestCase):
    def test_api_vide_ne_depublie_rien(self):
        with mock.patch.object(betagouv, "load", return_value=([], set())), mock.patch.object(sync, "run") as run:
            call_command("sync_betagouv", stdout=mock.MagicMock(), stderr=mock.MagicMock())
        run.assert_not_called()

    def test_dry_run_n_enregistre_rien_et_ne_telecharge_rien(self):
        products, inactive = betagouv.parse(STARTUPS, AUTHORS, "fab-geocommuns", TODAY)
        with (
            mock.patch.object(betagouv, "load", return_value=(products, inactive)),
            mock.patch.object(betagouv, "load_startup_images") as load_images,
        ):
            call_command("sync_betagouv", "--dry-run", stdout=mock.MagicMock())
        load_images.assert_not_called()
        self.assertFalse(ProduitsIndexPage.objects.filter(slug="produits").exists())
