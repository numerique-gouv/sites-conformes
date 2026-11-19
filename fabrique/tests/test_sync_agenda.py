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
        self.assertIn("Atelier adresses", reponse.content.decode())

        ical = self.client.get(index.url + "ical/")
        self.assertEqual(ical.status_code, 200)
        self.assertIn(b"SUMMARY:D\xc3\xa9mo du RNB", ical.content)
