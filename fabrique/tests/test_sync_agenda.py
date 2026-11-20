import copy
import io
from datetime import datetime, timedelta, timezone
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase
from wagtail.models import Site

from content_manager.models import ContentPage
from events.models import EventEntryPage, EventsIndexPage
from fabrique import agenda, grist
from fabrique.models import EtiquettesEvenement

DOC = "habcH4ftoLRf"
# Dans trois semaines, à l'heure pile : les événements restent « à venir » quel que soit le jour du test.
DEBUT = int((datetime.now(timezone.utc) + timedelta(days=21)).replace(minute=0, second=0, microsecond=0).timestamp())
OUTLOOK = "https://outlook.office.com/calendar/0/deeplink/compose?subject=Demo"


def ligne(id, titre, **fields):
    return {
        "id": id,
        "fields": {
            "Titre": titre,
            "Type": "Démo",
            "Equipe": ["L", "RNB"],
            "Serie": None,
            "Debut": DEBUT,
            "Fin": DEBUT + 5400,
            "Lieu": "",
            "Lien_visio": "https://webinaire.numerique.gouv.fr/rnb",
            "Lien_evenement": "",
            "Description": "## Au programme\n\nUne **démo** du RNB.",
            "Public": "Agents des collectivités",
            "Publie": True,
            "Annule": False,
            "Complet": False,
            "Etat": "Accès libre",
            "Lien_inscription": "",
            "Places_restantes": None,
            "Ajouter_outlook": OUTLOOK,
            **fields,
        },
    }


RECORDS = [
    ligne(1, "Démo du RNB"),
    ligne(
        2,
        "Atelier adresses",
        Type="Atelier",
        Equipe=["L", "BAN", "Fabrique de la donnée territoriale"],
        Serie=["L", "Forum de la donnée territoriale"],
        Lieu="IGN, Saint-Mandé",
        Lien_visio="",
        Lien_inscription="https://grist.numerique.gouv.fr/forms/abc",
        Etat="Inscriptions ouvertes",
        Places_restantes=12,
        Fin=None,
    ),
    ligne(3, "Brouillon", Publie=False),
    ligne(4, "", Publie=True),
]


class ParseTests(TestCase):
    def test_parse_garde_les_evenements_publies(self):
        evenements = grist.parse(RECORDS)
        self.assertEqual([e.titre for e in evenements], ["Démo du RNB", "Atelier adresses"])
        demo, atelier = evenements
        self.assertEqual(demo.debut, datetime.fromtimestamp(DEBUT, tz=timezone.utc))
        self.assertEqual(demo.equipes, ["RNB"])
        self.assertEqual(
            atelier.etiquettes,
            ["Atelier", "BAN", "Fabrique de la donnée territoriale", "Forum de la donnée territoriale"],
        )
        # Sans fin renseignée : une heure.
        self.assertEqual((atelier.fin - atelier.debut).total_seconds(), 3600)

    def test_source_url(self):
        url = grist.source_url("https://grist.numerique.gouv.fr", "fab-donnee-territoriale", DOC, 42)
        self.assertEqual(grist.row_id_from_source_url(url, DOC), 42)
        self.assertIsNone(grist.row_id_from_source_url(url, "autreDoc"))
        self.assertIsNone(grist.row_id_from_source_url("https://exemple.fr/page", DOC))
        self.assertIsNone(grist.row_id_from_source_url(None, DOC))


class SyncTests(TestCase):
    def setUp(self):
        self.root = Site.objects.get(is_default_site=True).root_page

    def run_sync(self, records=None):
        return agenda.run(grist.parse(copy.deepcopy(records if records is not None else RECORDS)), "agenda")

    def page(self, row_id):
        return next(
            p for p in EventEntryPage.objects.all() if grist.row_id_from_source_url(p.source_url, DOC) == row_id
        )

    def test_premiere_synchro(self):
        report = self.run_sync()
        self.assertEqual(report.created, ["Page Agenda", "Démo du RNB", "Atelier adresses"])

        index = EventsIndexPage.objects.get(slug="agenda")
        self.assertTrue(index.live)
        self.assertEqual(EventEntryPage.objects.child_of(index).live().count(), 2)

        demo = self.page(1)
        self.assertEqual(demo.title, "Démo du RNB")
        self.assertEqual(demo.location, "En ligne")
        self.assertIsNone(demo.registration_url)
        self.assertEqual(sorted(t.name for t in demo.tags.all()), ["Démo", "RNB"])
        types = [b.block_type for b in demo.body]
        self.assertEqual(types, ["paragraph", "markdown", "buttons_list"])
        boutons = [b.value["text"] for b in demo.body[2].value["buttons"]]
        self.assertEqual(boutons, ["Rejoindre la visio", "Ajouter à Outlook"])

        atelier = self.page(2)
        self.assertEqual(atelier.location, "IGN, Saint-Mandé")
        self.assertEqual(atelier.registration_url, "https://grist.numerique.gouv.fr/forms/abc")
        self.assertIn("Places restantes", atelier.body[0].value.source)

    def test_deuxieme_synchro_sans_changement(self):
        self.run_sync()
        revisions = self.page(1).revisions.count()
        report = self.run_sync()
        self.assertEqual(report.unchanged, ["Démo du RNB", "Atelier adresses"])
        self.assertEqual(self.page(1).revisions.count(), revisions)

    def test_type_et_equipes_gardes_pour_les_cartes(self):
        self.run_sync()
        atelier = EtiquettesEvenement.objects.get(page=self.page(2))
        self.assertEqual(atelier.type, "Atelier")
        self.assertEqual(atelier.equipes, ["BAN", "Fabrique de la donnée territoriale"])

        # Équipes changées dans Grist : étiquettes à jour.
        records = copy.deepcopy(RECORDS)
        records[1]["fields"].update(Type="Webinaire", Equipe=["L", "BAN"])
        self.run_sync(records)
        atelier.refresh_from_db()
        self.assertEqual((atelier.type, atelier.equipes), ("Webinaire", ["BAN"]))

    def test_etiquettes_ajoutees_sans_republier(self):
        # Pages synchronisées avant l'ajout des étiquettes sur les cartes : rattrapées sans nouvelle révision.
        self.run_sync()
        EtiquettesEvenement.objects.all().delete()
        revisions = self.page(1).revisions.count()
        report = self.run_sync()
        self.assertEqual(report.unchanged, ["Démo du RNB", "Atelier adresses"])
        self.assertEqual(self.page(1).revisions.count(), revisions)
        self.assertEqual(EtiquettesEvenement.objects.get(page=self.page(1)).equipes, ["RNB"])

    def test_mise_a_jour_annulation_et_blocs_manuels(self):
        self.run_sync()
        demo = self.page(1)
        # Un éditeur ajoute un bloc à la main, après les blocs synchronisés.
        demo.body = list(demo.body.raw_data) + [{"type": "paragraph", "id": "manuel", "value": "<p>Note</p>"}]
        demo.save_revision().publish()

        records = copy.deepcopy(RECORDS)
        records[0]["fields"].update(Annule=True, Ajouter_outlook="", Titre="Démo du RNB (v2)")
        report = self.run_sync(records)
        self.assertEqual(report.updated, ["Démo du RNB (v2)"])

        demo = self.page(1)
        self.assertEqual(demo.title, "Annulé : Démo du RNB (v2)")
        self.assertEqual([b.block_type for b in demo.body], ["alert", "paragraph", "markdown", "paragraph"])
        self.assertEqual(demo.body[-1].value.source, "<p>Note</p>")

    def test_depublication(self):
        self.run_sync()
        records = copy.deepcopy(RECORDS)
        records[1]["fields"]["Publie"] = False
        report = self.run_sync(records)
        self.assertEqual(report.unpublished, ["Atelier adresses"])
        self.assertFalse(self.page(2).live)

        # Republiée dans Grist : la même page revient en ligne.
        report = self.run_sync()
        self.assertEqual(report.updated, ["Atelier adresses"])
        self.assertTrue(self.page(2).live)
        self.assertEqual(EventEntryPage.objects.count(), 2)

    def test_brouillon_respecte(self):
        self.run_sync()
        demo = self.page(1)
        demo.title = "Titre en cours de modification"
        demo.save_revision()
        records = copy.deepcopy(RECORDS)
        records[0]["fields"]["Titre"] = "Nouveau titre"
        report = self.run_sync(records)
        self.assertEqual(report.skipped_drafts, ["Nouveau titre"])
        self.assertEqual(EventEntryPage.objects.get(id=demo.id).title, "Démo du RNB")

    def test_evenement_saisi_a_la_main_conserve(self):
        self.run_sync()
        index = EventsIndexPage.objects.get(slug="agenda")
        manuel = EventEntryPage(title="Événement manuel", slug="manuel")
        index.add_child(instance=manuel)
        manuel.save_revision().publish()
        self.run_sync([])
        self.assertTrue(EventEntryPage.objects.get(slug="manuel").live)

    def test_adresse_deja_prise(self):
        page = ContentPage(title="Agenda (iframe)", slug="agenda")
        self.root.add_child(instance=page)
        with self.assertRaisesMessage(RuntimeError, "n'est pas un calendrier"):
            self.run_sync()


@mock.patch.dict("os.environ", {"GRIST_API_KEY": "cle-de-test"})
class CommandTests(TestCase):
    def call(self, records, *args):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(grist, "fetch_records", return_value=copy.deepcopy(records)) as fetch:
            call_command("sync_agenda_grist", *args, stdout=out, stderr=err)
        return fetch, out.getvalue(), err.getvalue()

    def test_commande(self):
        fetch, out, _ = self.call(RECORDS)
        fetch.assert_called_once_with("https://grist.numerique.gouv.fr", DOC, "cle-de-test")
        self.assertIn("2 événements publiés sur 4 lignes", out)
        self.assertEqual(EventEntryPage.objects.live().count(), 2)

    def test_dry_run(self):
        _, out, _ = self.call(RECORDS, "--dry-run")
        self.assertIn("[simulation] Pages créées", out)
        self.assertEqual(EventEntryPage.objects.count(), 0)

    def test_table_vide_ne_vide_pas_l_agenda(self):
        self.call(RECORDS)
        _, _, err = self.call([])
        self.assertIn("synchronisation annulée", err)
        self.assertEqual(EventEntryPage.objects.live().count(), 2)

    def test_sans_cle(self):
        with mock.patch.dict("os.environ", {"GRIST_API_KEY": ""}):
            with self.assertRaisesMessage(CommandError, "GRIST_API_KEY"):
                call_command("sync_agenda_grist")

    def test_grist_injoignable(self):
        with mock.patch.object(grist, "fetch_records", side_effect=RuntimeError("HTTP 403")):
            with self.assertRaisesMessage(CommandError, "HTTP 403"):
                call_command("sync_agenda_grist", stdout=io.StringIO())


class RenduTests(TestCase):
    def test_pages_affichees(self):
        agenda.run(grist.parse(copy.deepcopy(RECORDS)), "agenda")
        index = EventsIndexPage.objects.get(slug="agenda")
        demo = EventEntryPage.objects.get(title="Démo du RNB")

        reponse = self.client.get(demo.url)
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        for texte in ("Rejoindre la visio", "Ajouter à Outlook", "Au programme", "Agents des collectivités"):
            self.assertIn(texte, contenu)

        reponse = self.client.get(index.url)
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn("Atelier adresses", contenu)
        # Sur chaque carte : le type de l'événement et les équipes concernées (pas les séries).
        cartes = contenu.split('class="fr-card fr-enlarge-link"')[1:]
        self.assertEqual(len(cartes), 2)
        demo_carte, atelier_carte = cartes
        self.assertIn('<span class="fr-sr-only">Type : </span>Démo', demo_carte)
        self.assertIn('<span class="fr-sr-only">Équipe : </span>RNB', demo_carte)
        self.assertIn('<span class="fr-sr-only">Type : </span>Atelier', atelier_carte)
        self.assertIn('<span class="fr-sr-only">Équipe : </span>BAN', atelier_carte)
        self.assertIn("Fabrique de la donnée territoriale", atelier_carte)
        self.assertNotIn("Forum de la donnée territoriale", atelier_carte.split("fr-card__header")[0])

        ical = self.client.get(index.url + "ical/")
        self.assertEqual(ical.status_code, 200)
        self.assertIn(b"SUMMARY:D\xc3\xa9mo du RNB", ical.content)


def png(couleur="red", taille=(64, 36)) -> bytes:
    from PIL import Image as PILImage

    tampon = io.BytesIO()
    PILImage.new("RGB", taille, couleur).save(tampon, format="PNG")
    return tampon.getvalue()


class FausseGrist:
    """Pièces jointes en mémoire, avec le compte des téléchargements."""

    def __init__(self, fichiers: dict[int, tuple[str, bytes]]):
        self.fichiers, self.telechargements = fichiers, []

    def infos(self, attachment_id):
        if attachment_id not in self.fichiers:
            return None
        nom, contenu = self.fichiers[attachment_id]
        return {"fileName": nom, "fileSize": len(contenu)}

    def download(self, attachment_id):
        self.telechargements.append(attachment_id)
        return self.fichiers[attachment_id][1]


class ImageTests(TestCase):
    def setUp(self):
        import tempfile

        from django.test import override_settings

        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        reglages = override_settings(MEDIA_ROOT=self.media.name)
        reglages.enable()
        self.addCleanup(reglages.disable)
        self.grist = FausseGrist({7: ("affiche.png", png()), 8: ("autre.png", png("blue")), 9: ("prog.pdf", b"%PDF")})

    def sync(self, image=None):
        records = copy.deepcopy(RECORDS)
        records[0]["fields"]["Image"] = ["L", image] if image else None
        return agenda.run(grist.parse(records), "agenda", pieces_jointes=self.grist)

    def demo(self):
        return EventEntryPage.objects.get(title="Démo du RNB")

    def test_image_importee_une_seule_fois(self):
        self.sync(7)
        image = self.demo().header_image
        self.assertIsNotNone(image)
        self.assertEqual(image.collection.name, "Agenda")
        self.assertEqual((image.width, image.height), (64, 36))
        self.assertIsNone(EventEntryPage.objects.get(title="Atelier adresses").header_image)

        report = self.sync(7)
        self.assertIn("Démo du RNB", report.unchanged)
        self.assertEqual(self.grist.telechargements, [7])

        # Liste : vignette réduite et entière, pas le fichier original.
        contenu = self.client.get(EventsIndexPage.objects.get(slug="agenda").url).content.decode()
        self.assertIn("fabrique-vignette", contenu)
        self.assertIn("fabrique/agenda.css", contenu)
        self.assertNotIn(image.file.url, contenu)
        self.assertIn(image.get_rendition("max-480x270").url, contenu)
        self.assertNotIn("{#", contenu)  # aucun commentaire de gabarit affiché

        # Page de l'événement : feuille de style qui retire le bandeau.
        contenu = self.client.get(self.demo().url).content.decode()
        self.assertIn("fabrique/agenda-evenement.css", contenu)
        self.assertNotIn("{#", contenu)

    def test_image_changee_puis_retiree(self):
        self.sync(7)
        self.sync(8)
        self.assertIn("-8-", self.demo().header_image.file.name)
        self.sync(None)
        self.assertIsNone(self.demo().header_image)

    def test_image_choisie_a_la_main_conservee(self):
        from wagtail.images import get_image_model
        from wagtail.images.tests.utils import get_test_image_file

        self.sync(None)
        manuelle = get_image_model().objects.create(title="Photo", file=get_test_image_file())
        demo = self.demo()
        demo.header_image = manuelle
        demo.save_revision().publish()

        self.sync(None)
        self.assertEqual(self.demo().header_image, manuelle)
        # Une image ajoutée ensuite dans Grist prend la place.
        self.sync(7)
        self.assertEqual(self.demo().header_image.collection.name, "Agenda")

    def test_fichier_qui_n_est_pas_une_image(self):
        self.sync(9)
        self.assertIsNone(self.demo().header_image)
        self.assertEqual(self.grist.telechargements, [])
