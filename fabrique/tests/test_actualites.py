import copy
import io
import json
from datetime import datetime, timezone
from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from wagtail.models import Site

from blog.models import BlogEntryPage, BlogIndexPage, Category
from fabrique import actualites, grist, newsletters

DOC = "habcH4ftoLRf"
PANORAMAX = newsletters.Compte("Panoramax", "BREVO_CLE_PANORAMAX", objet="Info Panoramax")
VOIES = newsletters.Compte("Voies locales", "BREVO_CLE_VOIES_LOCALES", objet="Info Voies locales")


def campagne(id, nom, objet, envoi, **autres):
    return {
        "id": id,
        "name": nom,
        "subject": objet,
        "status": "sent",
        "sentDate": envoi,
        "shareLink": f"https://r.brevo.example/{id}.html",
        "previewText": "",
        **autres,
    }


# Extrait des campagnes réelles de Panoramax : infolettres mensuelles et communications à écarter.
CAMPAGNES_PANORAMAX = [
    campagne(73, "20261130_Visio_Instances_entreprises", "Invitation visio Panoramax - 30/11", "2026-11-03T09:00:00Z"),
    campagne(
        65,
        "202610 Infolettre octobre",
        "Info Panoramax octobre 2026",
        "2026-10-30T09:00:00.000+01:00",
        previewText="Les nouveautés du mois",
    ),
    campagne(
        69,
        "202610_date de depot-zero-photo",
        "Problème lors du versement des photos dans Panoramax",
        "2026-10-16T09:00:00Z",
    ),
    campagne(68, "20261015_nouveaux-comptes", "Bienvenue dans Panoramax", "2026-10-16T08:00:00Z"),
    campagne(59, "202609 Infolettre septembre", "Info Panoramax septembre2026", "2026-09-24T09:00:00Z"),
    campagne(45, "20260622_Info_Fondation", "Info sur la Fondation Panoramax", "2026-06-24T09:00:00Z"),
]

# Voies locales : même objet chaque mois, et un renvoi correctif le 14 octobre.
CAMPAGNES_VOIES = [
    campagne(17, "202611_Infolettre", "Info Voies locales en commun", "2026-11-17T10:07:03Z"),
    campagne(16, "20261106_Replay_webinaire", "Webinaire Voies locales : les documents", "2026-11-06T12:09:24Z"),
    campagne(10, "202610_Corr-Info_Voies_Locales", "Info Voies locales en commun", "2026-10-14T14:00:00Z"),
    campagne(9, "202610_Info_Voies_Locales", "Info Voies locales en commun", "2026-10-14T09:00:00Z"),
]


class FausseBrevo:
    """API Brevo en mémoire : une liste de campagnes par clé, servie par pages de deux."""

    def __init__(self, comptes: dict[str, list[dict]]):
        self.comptes, self.appels = comptes, []

    def __call__(self, url, api_key=None, method="GET", payload=None, headers=None, **kwargs):
        cle = headers["api-key"]
        if cle not in self.comptes:
            raise RuntimeError("GET https://api.brevo.com/v3/emailCampaigns impossible : HTTP Error 401")
        params = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        self.appels.append(params)
        offset, limit = int(params["offset"]), 2
        campagnes = self.comptes[cle]
        return json.dumps({"campaigns": campagnes[offset : offset + limit], "count": len(campagnes)}).encode()


class NewslettersTests(SimpleTestCase):
    def test_tri_garde_uniquement_les_infolettres(self):
        tri = newsletters.trier(PANORAMAX, CAMPAGNES_PANORAMAX)
        self.assertEqual([c["id"] for c in tri.gardees], [59, 65])
        self.assertEqual(sorted(c["id"] for c in tri.ecartees), [45, 68, 69, 73])

    def test_renvoi_correctif(self):
        tri = newsletters.trier(VOIES, CAMPAGNES_VOIES)
        self.assertEqual([c["id"] for c in tri.gardees], [10, 17])
        self.assertEqual([c["id"] for c in tri.remplacees], [9])

    def test_titre_avec_le_mois(self):
        envoi = datetime(2026, 11, 17, 10, tzinfo=timezone.utc)
        self.assertEqual(
            newsletters.titre({"subject": "Info Voies locales en commun"}, envoi),
            "Info Voies locales en commun — novembre 2026",
        )
        self.assertEqual(
            newsletters.titre({"subject": "Info Panoramax Février 2026"}, envoi), "Info Panoramax Février 2026"
        )
        # Envoyée le 31 décembre à 23 h 30 à Paris : décembre, pas janvier.
        nuit = datetime(2026, 12, 31, 22, 30, tzinfo=timezone.utc)
        self.assertEqual(newsletters.titre({"subject": "Info"}, nuit), "Info — décembre 2026")

    def test_plan(self):
        records = [
            {"id": 1, "fields": {"Source": "Newsletter Brevo", "Source_uid": "brevo:voies-locales:9", "Publie": True}},
            {
                "id": 2,
                "fields": {"Source": "Newsletter Brevo", "Source_uid": "brevo:voies-locales:17", "Publie": False},
            },
        ]
        plan = newsletters.planifier(VOIES, newsletters.trier(VOIES, CAMPAGNES_VOIES), records)
        # La 17 existe déjà (dépubliée à la main) : elle n'est ni recréée ni republiée.
        self.assertEqual([a["Source_uid"] for a in plan.ajouts], ["brevo:voies-locales:10"])
        self.assertEqual(plan.depublications, [{"id": 1, "fields": {"Publie": False}}])
        ajout = plan.ajouts[0]
        self.assertEqual(ajout["Titre"], "Info Voies locales en commun — octobre 2026")
        self.assertEqual(ajout["Equipe"], ["L", "Voies locales"])
        self.assertEqual(ajout["Lien"], "https://r.brevo.example/10.html")
        self.assertTrue(ajout["Publie"])

    def test_sans_version_web_importee_non_publiee(self):
        sans_lien = campagne(1, "Infolettre", "Info Panoramax mai 2026", "2026-05-28T09:00:00Z", shareLink="")
        plan = newsletters.planifier(PANORAMAX, newsletters.trier(PANORAMAX, [sans_lien]), [])
        self.assertFalse(plan.ajouts[0]["Publie"])

    def test_lecture_de_toutes_les_pages(self):
        brevo = FausseBrevo({"cle": CAMPAGNES_PANORAMAX})
        depuis = datetime(2025, 11, 20, tzinfo=timezone.utc)
        campagnes = newsletters.lire_campagnes("cle", depuis, requete=brevo)
        self.assertEqual(len(campagnes), 6)
        self.assertEqual([a["offset"] for a in brevo.appels], ["0", "2", "4"])
        self.assertEqual(brevo.appels[0]["status"], "sent")
        self.assertEqual(brevo.appels[0]["startDate"], "2025-11-20T00:00:00.000Z")

    def test_configuration(self):
        self.assertEqual(newsletters.depuis_env(None), newsletters.PAR_DEFAUT)
        self.assertEqual(newsletters.depuis_env(""), [])
        comptes = newsletters.depuis_env(
            "BAN | BREVO_CLE_BAN | nom: adresse.data.gouv.fr; RNB|BREVO_CLE_RNB|objet: Info RNB"
        )
        self.assertEqual(comptes[0], newsletters.Compte("BAN", "BREVO_CLE_BAN", nom="adresse.data.gouv.fr"))
        self.assertEqual(comptes[1], newsletters.Compte("RNB", "BREVO_CLE_RNB", objet="Info RNB"))
        self.assertTrue(comptes[0].garde({"name": "adresse.data.gouv.fr - Le fil info juin 2026", "subject": "x"}))
        with self.assertRaises(ValueError):
            newsletters.depuis_env("BAN | BREVO_CLE_BAN")
        with self.assertRaises(ValueError):
            newsletters.depuis_env("BAN | BREVO_CLE_BAN | adresse.data.gouv.fr")


def actu(id, titre, **fields):
    return {
        "id": id,
        "fields": {
            "Titre": titre,
            "Date": datetime(2026, 11, 1, 9, tzinfo=timezone.utc).timestamp() + id,
            "Equipe": ["L", "RNB"],
            "Source": "Communiqué",
            "Publie": True,
            "Chapo": "Le RNB passe un cap.",
            "Corps": "## Ce qui change\n\nUn **nouvel** identifiant.",
            "Lien": "",
            "Image": None,
            "Source_uid": "",
            **fields,
        },
    }


RECORDS = [
    actu(1, "Le RNB atteint 50 millions de bâtiments"),
    actu(
        2,
        "Info Panoramax octobre 2026",
        Equipe=["L", "Panoramax"],
        Source="Newsletter Brevo",
        Chapo="",
        Corps="",
        Lien="https://r.brevo.example/65.html",
        Source_uid="brevo:panoramax:65",
    ),
    actu(3, "Brouillon", Publie=False),
    actu(4, "", Publie=True),
]


class ParseTests(SimpleTestCase):
    def test_parse_garde_les_actus_publiees(self):
        actus = actualites.parse(RECORDS)
        self.assertEqual(
            [a.titre for a in actus], ["Info Panoramax octobre 2026", "Le RNB atteint 50 millions de bâtiments"]
        )
        self.assertTrue(actus[0].newsletter)
        self.assertEqual(actus[1].equipes, ["RNB"])

    def test_source_url(self):
        source = actualites.Source()
        url = source.url(42)
        self.assertTrue(url.startswith("https://grist.numerique.gouv.fr/o/fab-donnee-territoriale/habcH4ftoLRf/"))
        self.assertEqual(grist.row_id_from_source_url(url, DOC), 42)


class SyncTests(TestCase):
    def setUp(self):
        self.root = Site.objects.get(is_default_site=True).root_page
        # Catégorie déjà présente sur le site, sous un autre nom que l'équipe Grist.
        Category.objects.create(name="Référentiel National des Bâtiments", slug="referentiel-national-du-batiment")

    def run_sync(self, records=None):
        return actualites.run(
            actualites.parse(copy.deepcopy(records if records is not None else RECORDS)), "actualites"
        )

    def page(self, row_id):
        return next(
            p for p in BlogEntryPage.objects.all() if grist.row_id_from_source_url(p.source_url, DOC) == row_id
        )

    def test_premiere_synchro(self):
        report = self.run_sync()
        self.assertEqual(
            report.created,
            [
                "Page Actualités",
                "Catégorie Panoramax",
                "Info Panoramax octobre 2026",
                "Le RNB atteint 50 millions de bâtiments",
            ],
        )
        index = BlogIndexPage.objects.get(slug="actualites")
        self.assertEqual(BlogEntryPage.objects.child_of(index).live().count(), 2)

        communique = self.page(1)
        self.assertEqual([b.block_type for b in communique.body], ["paragraph", "markdown"])
        self.assertEqual([c.slug for c in communique.blog_categories.all()], ["referentiel-national-du-batiment"])
        self.assertEqual(list(communique.tags.all()), [])
        self.assertEqual(communique.search_description, "Le RNB passe un cap.")

        lettre = self.page(2)
        self.assertEqual([b.block_type for b in lettre.body], ["buttons_list"])
        bouton = lettre.body[0].value["buttons"][0]
        self.assertEqual(
            (bouton.value["text"], bouton.value["external_url"]),
            ("Lire la newsletter", "https://r.brevo.example/65.html"),
        )
        self.assertEqual([c.name for c in lettre.blog_categories.all()], ["Panoramax"])
        self.assertEqual([t.name for t in lettre.tags.all()], ["Newsletter"])

    def test_deuxieme_synchro_sans_changement(self):
        self.run_sync()
        revisions = self.page(1).revisions.count()
        report = self.run_sync()
        self.assertEqual(
            sorted(report.unchanged), ["Info Panoramax octobre 2026", "Le RNB atteint 50 millions de bâtiments"]
        )
        self.assertEqual(self.page(1).revisions.count(), revisions)

    def test_page_actualites_existante_reutilisee(self):
        index = BlogIndexPage(title="Nos actus", slug="nos-actus")
        self.root.add_child(instance=index)
        report = self.run_sync()
        self.assertNotIn("Page Actualités", report.created)
        self.assertEqual(BlogEntryPage.objects.child_of(index).count(), 2)

    def test_mise_a_jour_et_blocs_manuels(self):
        self.run_sync()
        page = self.page(1)
        page.body = list(page.body.raw_data) + [{"type": "paragraph", "id": "manuel", "value": "<p>Note</p>"}]
        page.save_revision().publish()

        records = copy.deepcopy(RECORDS)
        records[0]["fields"].update(Titre="Le RNB atteint 51 millions", Equipe=["L", "RNB", "BAN"], Chapo="")
        report = self.run_sync(records)
        self.assertEqual(report.updated, ["Le RNB atteint 51 millions"])
        page = self.page(1)
        self.assertEqual([b.block_type for b in page.body], ["markdown", "paragraph"])
        self.assertEqual(page.body[-1].value.source, "<p>Note</p>")
        self.assertEqual(
            sorted(c.name for c in page.blog_categories.all()), ["BAN", "Référentiel National des Bâtiments"]
        )

    def test_depublication(self):
        self.run_sync()
        records = copy.deepcopy(RECORDS)
        records[1]["fields"]["Publie"] = False
        report = self.run_sync(records)
        self.assertEqual(report.unpublished, ["Info Panoramax octobre 2026"])
        self.assertFalse(self.page(2).live)
        report = self.run_sync()
        self.assertEqual(report.updated, ["Info Panoramax octobre 2026"])
        self.assertTrue(self.page(2).live)

    def test_brouillon_respecte(self):
        self.run_sync()
        page = self.page(1)
        page.title = "Titre en cours"
        page.save_revision()
        records = copy.deepcopy(RECORDS)
        records[0]["fields"]["Titre"] = "Nouveau titre"
        report = self.run_sync(records)
        self.assertEqual(report.skipped_drafts, ["Nouveau titre"])

    def test_article_saisi_a_la_main_conserve(self):
        self.run_sync()
        index = BlogIndexPage.objects.get(slug="actualites")
        manuel = BlogEntryPage(title="Article manuel", slug="manuel")
        index.add_child(instance=manuel)
        manuel.save_revision().publish()
        self.run_sync([])
        self.assertTrue(BlogEntryPage.objects.get(slug="manuel").live)


class FausseGrist:
    """Table Actus en mémoire, derrière les fonctions de lecture et d'écriture de grist."""

    def __init__(self, lignes=None):
        self.lignes: dict[int, dict] = {r["id"]: dict(r["fields"]) for r in (lignes or [])}

    def fetch_records(self, base, doc, key, table=grist.TABLE):
        assert table == grist.TABLE_ACTUS
        return [{"id": i, "fields": dict(f)} for i, f in self.lignes.items()]

    def add_records(self, base, doc, key, fields, lot=100, table=grist.TABLE):
        assert table == grist.TABLE_ACTUS
        for f in fields:
            self.lignes[max(self.lignes, default=0) + 1] = {"Date": None, **f}

    def update_records(self, base, doc, key, records, lot=100, table=grist.TABLE):
        for r in records:
            self.lignes[r["id"]].update(r["fields"])


ENV = {"GRIST_API_KEY": "cle-de-test", "BREVO_CLE_PANORAMAX": "cle-panoramax", "BREVO_CLE_VOIES_LOCALES": "cle-voies"}


@mock.patch.dict("os.environ", ENV, clear=False)
class CommandeTests(TestCase):
    def setUp(self):
        import os

        os.environ.pop("NEWSLETTERS_BREVO", None)
        self.grist = FausseGrist([RECORDS[0]])
        for nom in ("fetch_records", "add_records", "update_records"):
            patch = mock.patch.object(grist, nom, getattr(self.grist, nom))
            patch.start()
            self.addCleanup(patch.stop)
        self.brevo = FausseBrevo({"cle-panoramax": CAMPAGNES_PANORAMAX, "cle-voies": CAMPAGNES_VOIES})
        patch = mock.patch.object(grist, "_request", self.brevo)
        patch.start()
        self.addCleanup(patch.stop)

    def call(self, *args):
        out, err = io.StringIO(), io.StringIO()
        call_command("sync_actualites_grist", *args, "--jours", "3650", stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    def test_import_puis_publication(self):
        out, err = self.call()
        self.assertEqual(err, "")
        self.assertIn("Brevo Panoramax : 2 infolettres, 2 ajoutées", out)
        self.assertIn("Brevo Voies locales : 2 infolettres, 2 ajoutées", out)
        titres = sorted(f["Titre"] for f in self.grist.lignes.values())
        self.assertIn("Info Voies locales en commun — novembre 2026", titres)
        self.assertEqual(len(self.grist.lignes), 5)
        # Les infolettres importées arrivent sur le site dans le même passage.
        self.assertEqual(BlogEntryPage.objects.live().count(), 5)
        self.assertEqual(BlogEntryPage.objects.filter(tags__name="Newsletter").count(), 4)

        out, _ = self.call()
        self.assertIn("Brevo Panoramax : 2 infolettres, 0 ajoutées", out)
        self.assertEqual(len(self.grist.lignes), 5)

    def test_retouches_dans_grist_conservees(self):
        self.call()
        uid = "brevo:panoramax:65"
        ligne = next(f for f in self.grist.lignes.values() if f["Source_uid"] == uid)
        ligne.update(Titre="Panoramax en octobre", Chapo="Un mois chargé", Publie=False)
        self.call()
        ligne = next(f for f in self.grist.lignes.values() if f["Source_uid"] == uid)
        self.assertEqual((ligne["Titre"], ligne["Publie"]), ("Panoramax en octobre", False))
        self.assertFalse(BlogEntryPage.objects.filter(title="Panoramax en octobre").exists())

    def test_lister_n_ecrit_rien(self):
        out, _ = self.call("--lister")
        self.assertIn("Filtre : objet commence par « Info Panoramax »", out)
        self.assertIn("gardée", out)
        self.assertIn("écartée", out)
        self.assertIn("remplacée", out)
        self.assertEqual(len(self.grist.lignes), 1)
        self.assertFalse(BlogEntryPage.objects.exists())

    def test_cle_absente_ou_refusee(self):
        with mock.patch.dict("os.environ", {"BREVO_CLE_VOIES_LOCALES": "", "BREVO_CLE_PANORAMAX": "mauvaise"}):
            out, err = self.call()
        self.assertIn("Voies locales : non importé (variable BREVO_CLE_VOIES_LOCALES absente)", err)
        self.assertIn("Panoramax : non importé", err)
        # Le communiqué déjà dans Grist est tout de même publié.
        self.assertEqual(BlogEntryPage.objects.live().count(), 1)

    def test_sans_newsletters(self):
        self.call("--sans-newsletters")
        self.assertEqual(self.brevo.appels, [])
        self.assertEqual(BlogEntryPage.objects.live().count(), 1)

    def test_table_vide_ne_vide_pas_les_actualites(self):
        self.call("--sans-newsletters")
        self.grist.lignes.clear()
        _, err = self.call("--sans-newsletters")
        self.assertIn("Table Actus vide", err)
        self.assertEqual(BlogEntryPage.objects.live().count(), 1)


class RenduTests(TestCase):
    def test_pages_affichees(self):
        actualites.run(actualites.parse(copy.deepcopy(RECORDS)), "actualites")
        index = BlogIndexPage.objects.get(slug="actualites")
        communique = BlogEntryPage.objects.get(title="Le RNB atteint 50 millions de bâtiments")
        lettre = BlogEntryPage.objects.get(title="Info Panoramax octobre 2026")

        contenu = self.client.get(communique.url).content.decode()
        for texte in ("Le RNB passe un cap.", "Ce qui change", "<strong>nouvel</strong>"):
            self.assertIn(texte, contenu)

        reponse = self.client.get(lettre.url)
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('href="https://r.brevo.example/65.html"', reponse.content.decode())
        self.assertIn("Lire la newsletter", reponse.content.decode())

        reponse = self.client.get(index.url)
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn("Info Panoramax octobre 2026", contenu)
        self.assertIn("Le RNB atteint 50 millions de bâtiments", contenu)
        # Filtre par étiquette : seulement les infolettres.
        contenu = self.client.get(index.url + "?tag=newsletter").content.decode()
        self.assertIn("Info Panoramax octobre 2026", contenu)
        self.assertNotIn("Le RNB atteint 50 millions", contenu)
        # Filtre par catégorie (lien depuis la fiche produit) : seulement Panoramax.
        contenu = self.client.get(index.url + "?category=panoramax").content.decode()
        self.assertIn("Info Panoramax octobre 2026", contenu)
        self.assertNotIn("Le RNB atteint 50 millions", contenu)
