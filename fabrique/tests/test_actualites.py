import copy
import io
import json
from datetime import datetime, timezone
from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Site

from blog.models import BlogEntryPage, BlogIndexPage, Category
from content_manager.models import CmsDsfrConfig
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
        # Vignette entière, de même surface apparente que les autres : un logo carré fait 144 px de côté.
        image = get_image_model().objects.create(title="Logo carré", file=get_test_image_file(size=(400, 400)))
        lettre.header_image = image
        lettre.save_revision().publish()
        contenu = self.client.get(index.url).content.decode()
        self.assertIn('class="fr-card__img fabrique-vignette"', contenu)
        self.assertIn('style="width: 144px"', contenu)
        self.assertEqual(contenu.count("fabrique-vignette"), 1)  # le communiqué n'a pas d'image
        # Page de l'article : pas de bandeau recadré, l'image entière à côté du titre.
        contenu = self.client.get(lettre.url).content.decode()
        self.assertNotIn("cmsfr-hero", contenu)
        self.assertIn('class="fabrique-entete-actu__image"', contenu)
        self.assertNotIn("fill-1200x350", contenu)
        self.assertEqual(contenu.count("<h1"), 1)
        self.assertIn("Info Panoramax octobre 2026", contenu)
        self.assertIn("Publié le", contenu)
        # Sans image d'en-tête, le titre prend toute la largeur.
        contenu = self.client.get(communique.url).content.decode()
        self.assertNotIn("fabrique-entete-actu__image", contenu)
        self.assertIn('class="fr-col-12"', contenu)
        # Sans image : le logo du site (ici en longueur, 4:1 → 360 px de large).
        config = CmsDsfrConfig.for_site(Site.objects.get(is_default_site=True))
        config.operator_logo_file = get_image_model().objects.create(
            title="Logo de la Fabrique", file=get_test_image_file(size=(800, 200))
        )
        config.save()
        contenu = self.client.get(index.url).content.decode()
        self.assertEqual(contenu.count('class="fr-card__img fabrique-vignette"'), 2)
        self.assertIn('style="width: 144px"', contenu)
        self.assertIn('style="width: 360px"', contenu)
        # Filtre par étiquette : seulement les infolettres.
        contenu = self.client.get(index.url + "?tag=newsletter").content.decode()
        self.assertIn("Info Panoramax octobre 2026", contenu)
        self.assertNotIn("Le RNB atteint 50 millions", contenu)
        # Filtre par catégorie (lien depuis la fiche produit) : seulement Panoramax.
        contenu = self.client.get(index.url + "?category=panoramax").content.decode()
        self.assertIn("Info Panoramax octobre 2026", contenu)
        self.assertNotIn("Le RNB atteint 50 millions", contenu)


# ---------------------------------------------------------------------------
# Contenu des infolettres et doublons saisis à la main
# ---------------------------------------------------------------------------

from wagtail.contrib.redirects.models import Redirect  # noqa: E402

from fabrique.infolettre_html import en_markdown  # noqa: E402

IMAGE = "https://img.mailinblue.com/1/images/content_library/original/fondation.png"
HTML_INFOLETTRE = f"""<html><head><style>#outlook a {{ padding:0; }}</style></head><body>
<div style="display:none;mso-hide:all">Texte d'aperçu caché</div>
<table><tr><td><a href="{{{{ mirror }}}}">Voir la version en ligne</a></td></tr>
<tr><td><a href="https://panoramax.fr/"><img src="https://img.mailinblue.com/1/logo.png" width="50"></a></td></tr>
<tr><td><p><strong>Panoramax</strong></p><p><strong>L'alternative libre</strong></p>
<h1 style="font-weight:700"><span>Info Panoramax&nbsp;</span></h1><p><span>Avril 2026</span></p></td></tr>
<tr><td><p>Bonjour {{{{ contact.PRENOM }}}}, rendez-vous le <strong>lundi 13 avril&nbsp;</strong>et
<a href="https://peertube.example/v">son enregistrement&nbsp;</a>sur Peertube.</p><p><br></p></td></tr>
<tr><td><h2><span>[ <span>🚀&nbsp;Visio Fondation le 18 mai ]</span></span></h2>
<a href="https://forum.example/t/1"><img src="{IMAGE}" width="233"></a>
<p>Deux voies <strong>possibles</strong><strong> :</strong></p>
<ol><li>une association</li><li>un projet au sein de la <b>fondation INRIA</b></li></ol>
<ul><li><a href="https://forum.example/t/2">Lidar et Panoramax ?</a></li></ul>
<p>✔ Le <a href="https://forum.example">Forum</a><br>✔ Les <a href="https://docs.example">Docs</a></p></td></tr>
<tr><td><a href="https://www.linkedin.com/company/x"><img
  src="https://creative-assets.mailinblue.com/editor/social-icons/rounded_colored/linkedin_48px.png" width="48"></a>
<a href="https://mapstodon.space/@panoramax">
<img src="https://img.mailinblue.com/1/masto.png" width="48"></a></td></tr>
<tr><td><a href="https://panoramax.fr"><img src="https://img.mailinblue.com/1/logo.png" width="86"></a></td></tr>
<tr><td>Panoramax<br>73 avenue de Paris<br>94160 Saint Mandé</td></tr>
<tr><td><a href="mailto:contact@panoramax.fr">contact@panoramax.fr</a></td></tr>
<tr><td><center>Si vous souhaitez vous désinscrire de notre newsletter, cliquez <a href="{{{{ unsubscribe }}}}">ici</a>
</center></td></tr></table><img src="https://r.brevo.example/o.gif" width="1" height="1"></body></html>"""

MARKDOWN_ATTENDU = f"""Bonjour, rendez-vous le **lundi 13 avril** et [son enregistrement](https://peertube.example/v) \
sur Peertube.

## 🚀 Visio Fondation le 18 mai

[![]({IMAGE})](https://forum.example/t/1)

Deux voies **possibles** **:**

1. une association
2. un projet au sein de la **fondation INRIA**

- [Lidar et Panoramax ?](https://forum.example/t/2)

✔ Le [Forum](https://forum.example)

✔ Les [Docs](https://docs.example)"""


class InfolettreHtmlTests(SimpleTestCase):
    def test_conversion(self):
        self.assertEqual(en_markdown(HTML_INFOLETTRE, "Info Panoramax avril 2026"), MARKDOWN_ATTENDU)

    def test_sans_titre_reconnu_l_entete_est_garde(self):
        md = en_markdown(HTML_INFOLETTRE, "Autre chose")
        self.assertTrue(md.startswith("**Panoramax**"))

    def test_html_vide(self):
        self.assertEqual(en_markdown("", "x"), "")
        self.assertEqual(en_markdown("<html><body><img src='https://x/p.gif' width='1'></body></html>", "x"), "")


class CorpsNewslettersTests(SimpleTestCase):
    def test_import_avec_le_contenu(self):
        lettre = campagne(32, "202604 Infolettre avril", "Info Panoramax avril 2026", "2026-04-28T09:00:00Z",
                          htmlContent=HTML_INFOLETTRE)  # fmt: skip
        plan = newsletters.planifier(PANORAMAX, newsletters.trier(PANORAMAX, [lettre]), [])
        self.assertEqual(plan.ajouts[0]["Corps"], MARKDOWN_ATTENDU)

    def test_corps_vide_complete_corps_retouche_garde(self):
        lettres = [
            campagne(
                32, "Infolettre", "Info Panoramax avril 2026", "2026-04-28T09:00:00Z", htmlContent=HTML_INFOLETTRE
            ),
            campagne(39, "Infolettre", "Info Panoramax mai 2026", "2026-05-28T09:00:00Z", htmlContent=HTML_INFOLETTRE),
        ]
        records = [
            {"id": 4, "fields": {"Source": "Newsletter Brevo", "Source_uid": "brevo:panoramax:32",
                                 "Titre": "Info Panoramax avril 2026", "Corps": ""}},
            {"id": 5, "fields": {"Source": "Newsletter Brevo", "Source_uid": "brevo:panoramax:39",
                                 "Titre": "Info Panoramax mai 2026", "Corps": "Texte retouché"}},
        ]  # fmt: skip
        plan = newsletters.planifier(PANORAMAX, newsletters.trier(PANORAMAX, lettres), records)
        self.assertEqual(plan.ajouts, [])
        self.assertEqual(plan.completions, [{"id": 4, "fields": {"Corps": MARKDOWN_ATTENDU}}])


class DoublonsTests(TestCase):
    def setUp(self):
        self.index = BlogIndexPage(title="Les actualités", slug="les-actualites")
        Site.objects.get(is_default_site=True).root_page.add_child(instance=self.index)
        self.panoramax = Category.objects.create(name="Panoramax", slug="panoramax")

    def manuel(self, titre, slug, jour, contenu, categorie=None):
        page = BlogEntryPage(
            title=titre, slug=slug, date=datetime(2026, 4, jour, 8, tzinfo=timezone.utc),
            body=[{"type": "html", "id": "colle", "value": contenu}],
        )  # fmt: skip
        actualites._set_categories(page, [(categorie or self.panoramax).id])
        self.index.add_child(instance=page)
        page.save_revision().publish()
        return page

    def lettre(self, corps=f"Intro\n\n![]({IMAGE})"):
        return actu(
            7, "Info Panoramax avril 2026", Date=datetime(2026, 4, 28, 9, tzinfo=timezone.utc).timestamp(),
            Equipe=["L", "Panoramax"], Source="Newsletter Brevo", Chapo="", Corps=corps,
            Lien="https://r.brevo.example/32.html",
        )  # fmt: skip

    def test_article_manuel_depublie_et_redirige(self):
        doublon = self.manuel("Info Panoramax - 28/04/2026", "info-panoramax-28042026", 28, f'<img src="{IMAGE}">')
        autre_jour = self.manuel("Info Panoramax - 13/02/2026", "info-panoramax-autre", 13, f'<img src="{IMAGE}">')
        autre_sujet = self.manuel("Panoramax au salon", "salon", 28, "<p>Un autre article</p>")
        report = actualites.run(actualites.parse([self.lettre()]), "les-actualites")

        self.assertEqual(
            report.unpublished, ["Info Panoramax - 28/04/2026 (doublon de « Info Panoramax avril 2026 »)"]
        )
        doublon.refresh_from_db()
        self.assertFalse(doublon.live)
        self.assertTrue(BlogEntryPage.objects.get(pk=autre_jour.pk).live)
        self.assertTrue(BlogEntryPage.objects.get(pk=autre_sujet.pk).live)

        nouvelle = BlogEntryPage.objects.get(title="Info Panoramax avril 2026")
        redirection = Redirect.objects.get(old_path="/les-actualites/info-panoramax-28042026")
        self.assertEqual(redirection.redirect_page_id, nouvelle.pk)
        reponse = self.client.get("/les-actualites/info-panoramax-28042026/")
        self.assertRedirects(reponse, nouvelle.url, status_code=301, fetch_redirect_response=False)
        self.assertEqual(self.client.get(nouvelle.url).status_code, 200)

        # Au passage suivant, plus rien à faire.
        report = actualites.run(actualites.parse([self.lettre()]), "les-actualites")
        self.assertEqual(report.unpublished, [])

    def test_sans_image_le_titre_suffit(self):
        doublon = self.manuel("Info Panoramax - 28/04/2026", "manuel", 28, "<p>Copie</p>")
        actualites.run(actualites.parse([self.lettre(corps="")]), "les-actualites")
        doublon.refresh_from_db()
        self.assertFalse(doublon.live)

    def test_autre_equipe_et_communique_non_concernes(self):
        rnb = Category.objects.create(name="RNB", slug="referentiel-national-du-batiment")
        page = self.manuel("Info Panoramax - 28/04/2026", "rnb", 28, f'<img src="{IMAGE}">', categorie=rnb)
        communique = self.lettre()
        communique["fields"]["Source"] = "Communiqué"
        actualites.run(actualites.parse([communique]), "les-actualites")
        self.assertTrue(BlogEntryPage.objects.get(pk=page.pk).live)
        actualites.run(actualites.parse([self.lettre()]), "les-actualites")
        self.assertTrue(BlogEntryPage.objects.get(pk=page.pk).live)


class ImagesDuTexteTests(TestCase):
    """Les images des infolettres sont rapatriées dans la médiathèque : aucune image hébergée chez un tiers."""

    def setUp(self):
        from wagtail.images import get_image_model
        from wagtail.images.tests.utils import get_test_image_file

        from fabrique.models import ImageImportee

        self.appels = []

        def importer(url, titre, collection_name=None):
            self.appels.append((url, collection_name))
            image = get_image_model().objects.create(title=titre, file=get_test_image_file())
            ImageImportee.objects.create(url=url, empreinte="x", image=image)
            return image

        self.importer = importer
        corps = (
            "Intro\n\n"
            "[![Fondation](https://img.mailinblue.com/1/fondation.png)](https://forum.example/t/1)\n\n"
            "Texte avec ![une icône](https://img.mailinblue.com/1/icone.png) au milieu.\n\n"
            "![](https://img.mailinblue.com/1/carte.png)"
        )
        self.records = [
            actu(
                2, "Info Panoramax octobre 2026", Equipe=["L", "Panoramax"], Source="Newsletter Brevo", Chapo="",
                Corps=corps, Lien="https://r.brevo.example/65.html",
            )
        ]  # fmt: skip

    def run_sync(self, telecharger=True):
        corps = actualites.ImagesCorps(telecharger=telecharger, importer=self.importer)
        return actualites.run(actualites.parse(copy.deepcopy(self.records)), "actualites", images_corps=corps)

    def test_images_en_blocs_de_la_mediatheque(self):
        self.run_sync()
        page = BlogEntryPage.objects.get(title="Info Panoramax octobre 2026")
        self.assertEqual([b.block_type for b in page.body], ["buttons_list", "markdown", "image", "markdown", "image"])
        self.assertEqual(page.body[0].value["buttons"][0].value["text"], "Voir la version e-mail")
        image = page.body[2].value
        self.assertEqual((image["alt"], image["url"]), ("Fondation", "https://forum.example/t/1"))
        self.assertEqual(image["width"], "fr-content-media--sm")
        self.assertEqual(page.body[3].value, "Texte avec une icône au milieu.")
        self.assertEqual([c for _, c in self.appels], ["Actualités", "Actualités"])

        contenu = self.client.get(page.url).content.decode()
        self.assertNotIn("mailinblue", contenu)
        self.assertIn("fr-content-media--sm", contenu)
        self.assertIn("fr-responsive-img", contenu)

    def test_image_deja_importee_non_retelechargee(self):
        self.run_sync()
        revisions = BlogEntryPage.objects.get(title="Info Panoramax octobre 2026").revisions.count()
        report = self.run_sync()
        self.assertEqual(len(self.appels), 2)
        self.assertEqual(report.unchanged, ["Info Panoramax octobre 2026"])
        page = BlogEntryPage.objects.get(title="Info Panoramax octobre 2026")
        self.assertEqual(page.revisions.count(), revisions)

    def test_simulation_sans_telechargement(self):
        self.run_sync(telecharger=False)
        self.assertEqual(self.appels, [])
        page = BlogEntryPage.objects.get(title="Info Panoramax octobre 2026")
        self.assertEqual([b.block_type for b in page.body], ["buttons_list", "markdown", "markdown"])
        self.assertNotIn("mailinblue", self.client.get(page.url).content.decode())


class VoiesLocalesTests(TestCase):
    """Gabarit d'e-mail de Voies locales : bannière puis intertitre « Voies locales en commun »."""

    HTML = """<html><body><table>
<tr><td><img src="https://img.mailinblue.com/2/banniere.png"></td></tr>
<tr><td><h2>Voies locales en commun</h2><p>Ce mois-ci le programme a passé un cap :</p></td></tr>
<tr><td><h2>L'outil de saisie des voies est en test !</h2>
<img src="https://img.mailinblue.com/2/outil.png" width="300">
<p>Des séances de tests ont lieu.</p></td></tr></table></body></html>"""

    def test_entete_court_retire(self):
        md = en_markdown(self.HTML, "Info Voies locales en commun — novembre 2026")
        self.assertTrue(md.startswith("Ce mois-ci le programme a passé un cap :"), md)
        self.assertNotIn("banniere", md)
        self.assertIn("outil.png", md)

    def test_chapo_qui_repete_le_titre_ignore(self):
        records = [
            actu(1, "Info Voies locales en commun — novembre 2026", Equipe=["L", "Voies locales"],
                 Source="Newsletter Brevo", Chapo="Info Voies locales en commun", Corps="Le programme a passé un cap.")
        ]  # fmt: skip
        actualites.run(actualites.parse(records), "actualites")
        page = BlogEntryPage.objects.get(title="Info Voies locales en commun — novembre 2026")
        self.assertEqual([b.block_type for b in page.body], ["markdown"])
        self.assertEqual(page.search_description, "Le programme a passé un cap.")
