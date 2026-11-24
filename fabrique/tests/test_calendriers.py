import io
import json
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from events.models import EventEntryPage
from fabrique import calendriers, grist

PARIS = ZoneInfo("Europe/Paris")
PANORAMAX = calendriers.PAR_DEFAUT[0]

ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//SabreDAV//SabreDAV//EN
BEGIN:VTIMEZONE
TZID:Europe/Paris
BEGIN:STANDARD
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
BEGIN:DAYLIGHT
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
END:VTIMEZONE
BEGIN:VEVENT
UID:statuts
DTSTART;TZID=Europe/Paris:20261123T170000
DTEND;TZID=Europe/Paris:20261123T183000
SUMMARY:Panoramax Foundation : statutes
LOCATION:https://visio.numerique.gouv.fr/yzn-vxeb-xxo
CLASS:PUBLIC
END:VEVENT
BEGIN:VEVENT
UID:salon
DTSTART;VALUE=DATE:20261124
DTEND;VALUE=DATE:20261127
SUMMARY:Salon des Maires
URL:https://www.salondesmaires.com/
END:VEVENT
BEGIN:VEVENT
UID:echange
DTSTART;TZID=Europe/Paris:20261214T170000
DTEND;TZID=Europe/Paris:20261214T183000
SUMMARY:Echange mensuel francophone
LOCATION:Jitsi
DESCRIPTION:Echange mensuel sur Jitsi : https://meet.jit.si/panoramax\\nVen
 ez nombreux\\, merci !
END:VEVENT
BEGIN:VEVENT
UID:hackathon
DTSTART;TZID=Europe/Paris:20261005T090000
DTEND;TZID=Europe/Paris:20261009T170000
SUMMARY:Hackathon - Fondation Free / \xc3\x89cole 42
LOCATION:Ol\xc3\xa9ron
STATUS:CANCELLED
END:VEVENT
BEGIN:VEVENT
UID:prive
DTSTART;TZID=Europe/Paris:20261201T100000
SUMMARY:Rendez-vous priv\xc3\xa9
CLASS:PRIVATE
END:VEVENT
END:VCALENDAR
"""


def ts(*args):
    return datetime(*args, tzinfo=PARIS).timestamp()


class LectureTests(SimpleTestCase):
    def setUp(self):
        self.evenements = {e["uid"]: e for e in calendriers.lire(ICS)}

    def test_evenements_publics_seulement(self):
        self.assertEqual(set(self.evenements), {"statuts", "salon", "echange", "hackathon"})

    def test_heures_et_lieu_en_lien(self):
        e = self.evenements["statuts"]
        self.assertEqual((e["Debut"], e["Fin"]), (ts(2026, 11, 23, 17), ts(2026, 11, 23, 18, 30)))
        self.assertEqual((e["Lieu"], e["Lien_visio"]), ("", "https://visio.numerique.gouv.fr/yzn-vxeb-xxo"))

    def test_journees_entieres(self):
        e = self.evenements["salon"]
        self.assertEqual(e["Debut"], ts(2026, 11, 24, 0, 0))
        self.assertEqual(e["Fin"], ts(2026, 11, 26, 23, 59))  # fin iCal exclusive : le 27 n'est pas compris
        self.assertEqual(e["Lien_evenement"], "https://www.salondesmaires.com/")

    def test_visio_trouvee_dans_la_description(self):
        e = self.evenements["echange"]
        self.assertEqual((e["Lieu"], e["Lien_visio"]), ("", "https://meet.jit.si/panoramax"))
        self.assertEqual(
            e["Description"], "Echange mensuel sur Jitsi : https://meet.jit.si/panoramax  \nVenez nombreux, merci !"
        )

    def test_annulation_et_lieu_texte(self):
        e = self.evenements["hackathon"]
        self.assertTrue(e["Annule"])
        self.assertEqual((e["Lieu"], e["Lien_visio"]), ("Oléron", ""))

    def test_configuration(self):
        self.assertEqual(calendriers.depuis_env(None), calendriers.PAR_DEFAUT)
        self.assertEqual([c.equipe for c in calendriers.PAR_DEFAUT], ["Panoramax", "Voies locales", "BAN"])
        self.assertEqual(calendriers.PAR_DEFAUT[2].format, "ban")
        (ban,) = calendriers.depuis_env("Agenda BAN | BAN | https://exemple.fr/api/events | ban")
        self.assertEqual(ban.format, "ban")
        with self.assertRaises(ValueError):
            calendriers.depuis_env("Agenda BAN | BAN | https://exemple.fr/api/events | xml")
        self.assertEqual(calendriers.depuis_env(""), [])
        liste = calendriers.depuis_env("Framagenda BAN | BAN | https://exemple.fr/ban.ics; RNB | RNB | https://x/rnb")
        self.assertEqual([c.equipe for c in liste], ["BAN", "RNB"])
        with self.assertRaises(ValueError):
            calendriers.depuis_env("pas de séparateur")


# Flux iCal d'un site Sites Faciles (ex. Voies locales en commun) : heures en UTC, identifiant = n° de page,
# pas de description ; seulement les événements à venir.
ICS_SITES_FACILES = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Sites Faciles//
BEGIN:VEVENT
SUMMARY:Commission Besoins et usages du CNIG
DTSTART:20261123T120000Z
DTEND:20261123T140000Z
DTSTAMP:20261120T100000Z
UID:51
LOCATION:Visio
END:VEVENT
END:VCALENDAR
"""


class SitesFacilesTests(SimpleTestCase):
    def test_flux_sites_faciles(self):
        (e,) = calendriers.lire(ICS_SITES_FACILES)
        self.assertEqual(e["uid"], "51")
        self.assertEqual((e["Debut"], e["Fin"]), (ts(2026, 11, 23, 13), ts(2026, 11, 23, 15)))
        # « Visio » sans lien dans la description : reste un lieu.
        self.assertEqual((e["Lieu"], e["Lien_visio"], e["Description"]), ("Visio", "", ""))
        voies_locales = calendriers.PAR_DEFAUT[1]
        (ajout,) = calendriers.planifier(voies_locales, [e], []).ajouts
        self.assertEqual((ajout["Source"], ajout["Equipe"]), ("Site Voies locales", ["L", "Voies locales"]))


class PlanTests(SimpleTestCase):
    def setUp(self):
        self.evenements = calendriers.lire(ICS)

    def test_premier_import(self):
        plan = calendriers.planifier(PANORAMAX, self.evenements, [])
        self.assertEqual(len(plan.ajouts), 4)
        ajout = next(a for a in plan.ajouts if a["Source_uid"] == "salon")
        self.assertEqual(ajout["Source"], "Framagenda Panoramax")
        self.assertEqual(ajout["Equipe"], ["L", "Panoramax"])
        self.assertIs(ajout["Publie"], True)
        self.assertFalse(plan.mises_a_jour or plan.depublications)

    def records(self, **modifs):
        """Lignes Grist telles qu'après un premier import, puis modifiées par les éditeurs."""
        lignes = []
        for i, a in enumerate(calendriers.planifier(PANORAMAX, self.evenements, []).ajouts, start=1):
            fields = {**a, **modifs.get(a["Source_uid"], {})}
            lignes.append({"id": i, "fields": fields})
        return lignes

    def test_rien_a_faire(self):
        self.assertFalse(calendriers.planifier(PANORAMAX, self.evenements, self.records()))

    def test_champs_du_calendrier_restaures_les_autres_gardes(self):
        records = self.records(
            statuts={"Titre": "Titre modifié dans Grist", "Type": "Démo", "Publie": False, "Description": ""}
        )
        plan = calendriers.planifier(PANORAMAX, self.evenements, records)
        self.assertEqual(plan.mises_a_jour, [{"id": 1, "fields": {"Titre": "Panoramax Foundation : statutes"}}])
        self.assertFalse(plan.ajouts)

    def test_evenement_retire_du_calendrier(self):
        maintenant = ts(2026, 11, 20, 12)
        records = self.records()
        source = {"Source": "Framagenda Panoramax", "Publie": True}
        records.append({"id": 99, "fields": {**source, "Source_uid": "a-venir", "Debut": ts(2026, 12, 1, 10)}})
        # Passé : reste publié même s'il n'est plus dans le flux (flux limités aux événements à venir).
        records.append({"id": 98, "fields": {**source, "Source_uid": "passe", "Fin": ts(2026, 11, 2, 12)}})
        records.append({"id": 100, "fields": {"Titre": "Saisi à la main", "Publie": True}})
        plan = calendriers.planifier(PANORAMAX, self.evenements, records, maintenant=maintenant)
        self.assertEqual(plan.depublications, [{"id": 99, "fields": {"Publie": False}}])

    def test_calendrier_vide_ne_depublie_rien(self):
        self.assertFalse(calendriers.planifier(PANORAMAX, [], self.records()))


class FausseGrist:
    """Table Evenements en mémoire, derrière les fonctions d'écriture et de lecture de grist."""

    def __init__(self):
        self.lignes: dict[int, dict] = {}

    def fetch_records(self, *args):
        return [{"id": i, "fields": dict(f)} for i, f in self.lignes.items()]

    def add_records(self, base, doc, key, fields):
        for f in fields:
            self.lignes[len(self.lignes) + 1] = dict(f)

    def update_records(self, base, doc, key, records):
        for r in records:
            self.lignes[r["id"]].update(r["fields"])


@mock.patch.dict("os.environ", {"GRIST_API_KEY": "cle-de-test"}, clear=False)
class ImportCommandeTests(TestCase):
    def setUp(self):
        import os

        os.environ["AGENDA_CALENDRIERS"] = f"{PANORAMAX.source} | {PANORAMAX.equipe} | {PANORAMAX.url}"
        self.addCleanup(os.environ.pop, "AGENDA_CALENDRIERS", None)
        self.grist = FausseGrist()
        for nom in ("fetch_records", "add_records", "update_records"):
            patch = mock.patch.object(grist, nom, getattr(self.grist, nom))
            patch.start()
            self.addCleanup(patch.stop)
        patch = mock.patch.object(grist, "_get", return_value=ICS)
        self.telechargement = patch.start()
        self.addCleanup(patch.stop)

    def call(self, *args):
        out, err = io.StringIO(), io.StringIO()
        call_command("sync_agenda_grist", *args, stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    def test_import_puis_publication_sur_le_site(self):
        out, _ = self.call()
        self.telechargement.assert_called_once_with(PANORAMAX.url)
        self.assertIn("Calendrier Framagenda Panoramax : 4 ajoutés, 0 mis à jour, 0 dépubliés", out)
        self.assertEqual(len(self.grist.lignes), 4)
        # Les événements importés arrivent sur le site dans le même passage.
        self.assertEqual(EventEntryPage.objects.live().count(), 4)
        salon = EventEntryPage.objects.get(title="Salon des Maires")
        self.assertEqual([t.name for t in salon.tags.all()], ["Panoramax"])

        out, _ = self.call()
        self.assertIn("0 ajoutés, 0 mis à jour, 0 dépubliés", out)

    def test_simulation_n_ecrit_pas_dans_grist(self):
        out, _ = self.call("--dry-run")
        self.assertIn("[simulation] Calendrier Framagenda Panoramax : 4 ajoutés", out)
        self.assertEqual(self.grist.lignes, {})

    def test_calendrier_injoignable(self):
        self.telechargement.side_effect = RuntimeError("HTTP 503")
        _, err = self.call()
        self.assertIn("Framagenda Panoramax : non importé (HTTP 503)", err)
        self.assertEqual(self.grist.lignes, {})

    def test_sans_calendriers(self):
        self.call("--sans-calendriers")
        self.telechargement.assert_not_called()


# Extrait de l'API des événements de la BAN (bal-admin.adresse.data.gouv.fr/api/events), champs réels.
API_BAN = json.dumps(
    [
        {
            "id": "65afd71b2822a2f19e2e7c09",
            "title": "Webinaire Mes Adresses",
            "subtitle": "Je débute sur Mes Adresses",
            "description": "Rappel des principales fonctionnalités.",
            "type": "formation",
            "target": "communes",
            "date": "2022-09-08",
            "tags": ["Base Adresse Locale", "Commune"],
            "isOnlineOnly": True,
            "address": None,
            "href": "https://cryptpad.fr/form/#/2/form/view/KFNeMiPGM/embed/",
            "isSubscriptionClosed": False,
            "startHour": "14:00",
            "endHour": "15:30",
        },
        {
            "id": "6af9e4be9a3e799db9553fcb",
            "title": "Webinaire Mes Adresses - NIVEAU 2",
            "subtitle": "Formation approndie",
            "description": "Pour se perfectionner sur Mes Adresses",
            "type": "formation-lvl2",
            "target": "communes",
            "date": "2026-12-10",
            "isOnlineOnly": True,
            "address": None,
            "href": "https://webinaire.numerique.gouv.fr/meeting/signin/invite/62207/hash/2971a9",
            "startHour": "10:00",
            "endHour": "11:30",
        },
        {
            "id": "6af9e4349a3e799db9553fc9",
            "title": "Événement Partenaire de la Charte de la Base Adresse Locale",
            "subtitle": None,
            "description": None,
            "type": "partenaire",
            "target": "Communes, EPCI, départements, IDG et entreprises partenaires de la Charte",
            "date": "2026-12-15",
            "isOnlineOnly": False,
            "address": {"nom": "Salle des fêtes", "commune": "Saint-Mandé"},
            "href": "https://adresse.data.gouv.fr/",
            "isSubscriptionClosed": True,
            "startHour": "10:00",
            "endHour": None,
        },
        {"id": "sans-date", "title": "Sans date", "date": None},
    ]
).encode()


class BanTests(SimpleTestCase):
    def setUp(self):
        self.evenements = {e["uid"]: e for e in calendriers.lire_ban(API_BAN)}

    def test_lecture(self):
        self.assertEqual(len(self.evenements), 3)  # l'événement sans date est ignoré
        n2 = self.evenements["6af9e4be9a3e799db9553fcb"]
        self.assertEqual((n2["Debut"], n2["Fin"]), (ts(2026, 12, 10, 10), ts(2026, 12, 10, 11, 30)))
        self.assertEqual(
            n2["Lien_visio"], "https://webinaire.numerique.gouv.fr/meeting/signin/invite/62207/hash/2971a9"
        )
        self.assertEqual((n2["Lien_evenement"], n2["Lieu"], n2["Public"]), ("", "", "communes"))
        self.assertEqual(n2["Description"], "**Formation approndie**\n\nPour se perfectionner sur Mes Adresses")
        self.assertEqual(n2["creation"], {"Type": "Formation"})

    def test_formulaire_adresse_et_heure_de_fin_absente(self):
        ancien = self.evenements["65afd71b2822a2f19e2e7c09"]
        self.assertEqual(
            (ancien["Lien_visio"], ancien["Lien_evenement"]),
            ("", "https://cryptpad.fr/form/#/2/form/view/KFNeMiPGM/embed/"),
        )
        partenaire = self.evenements["6af9e4349a3e799db9553fc9"]
        self.assertEqual(partenaire["Lieu"], "Salle des fêtes, Saint-Mandé")
        self.assertEqual(partenaire["Fin"], ts(2026, 12, 15, 11))  # une heure par défaut
        self.assertEqual(partenaire["Description"], "")
        self.assertEqual(partenaire["creation"], {"Type": "Rencontre communauté"})

    def test_plan(self):
        ban = calendriers.PAR_DEFAUT[2]
        evenements = calendriers.lire_ban(API_BAN)
        plan = calendriers.planifier(ban, evenements, [])
        ajout = next(a for a in plan.ajouts if a["Source_uid"] == "6af9e4be9a3e799db9553fcb")
        self.assertEqual((ajout["Source"], ajout["Equipe"], ajout["Type"]), ("Agenda BAN", ["L", "BAN"], "Formation"))
        self.assertEqual(ajout["Public"], "communes")
        self.assertNotIn("creation", ajout)
        # Ensuite : le public suit la source, le type reste aux éditeurs.
        records = [
            {"id": i, "fields": {**a, "Type": "Webinaire", "Public": "Tout le monde"}}
            for i, a in enumerate(plan.ajouts, 1)
        ]
        maj = calendriers.planifier(ban, evenements, records).mises_a_jour
        self.assertEqual({tuple(m["fields"]) for m in maj}, {("Public",)})
