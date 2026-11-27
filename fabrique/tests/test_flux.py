from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from django.utils.text import slugify
from icalendar import Calendar
from wagtail.models import Site

from events.models import EventEntryPage, EventsIndexPage
from fabrique.models import EtiquettesEvenement


class FluxTests(TestCase):
    def setUp(self):
        root = Site.objects.get(is_default_site=True).root_page
        self.index = EventsIndexPage(title="Agenda", slug="agenda")
        root.add_child(instance=self.index)
        self.index.save_revision().publish()
        maintenant = timezone.now()
        for titre, jours, type_, equipes in [
            ("Collectif vigie", 10, "Rencontre", ["Fabrique de la donnée territoriale"]),
            ("Comité d'investissement RNB", 12, "Comité d'investissement", ["RNB"]),
            ("Échange mensuel Panoramax", 14, "Webinaire", ["Panoramax"]),
            ("Annulé : Démo BAN", 16, "Démo", ["BAN", "Fabrique de la donnée territoriale"]),
            ("Atelier passé", -30, "Atelier", ["Fabrique de la donnée territoriale"]),
            ("Très ancien", -200, "Atelier", ["Fabrique de la donnée territoriale"]),
            ("Saisi dans Wagtail", 20, None, None),
        ]:
            debut = maintenant + timedelta(days=jours)
            page = EventEntryPage(
                title=titre, slug=slugify(titre), event_date_start=debut, event_date_end=debut + timedelta(hours=1)
            )
            page.location = "Visio"
            self.index.add_child(instance=page)
            page.save_revision().publish()
            if equipes is not None:
                EtiquettesEvenement.objects.create(page=page, type=type_, equipes=equipes)

    def flux(self, nom):
        reponse = self.client.get(f"/flux/{nom}.ics")
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse["Content-Type"].startswith("text/calendar"))
        return Calendar.from_ical(reponse.content)

    def titres(self, cal):
        return [str(e["SUMMARY"]) for e in cal.walk("VEVENT")]

    def test_essentiel(self):
        cal = self.flux("agenda-fabrique")
        self.assertEqual(str(cal["X-WR-CALNAME"]), "Agenda de la Fabrique de la donnée territoriale")
        self.assertEqual(
            self.titres(cal),
            ["Atelier passé", "Collectif vigie", "Comité d'investissement RNB", "Annulé : Démo BAN", "Saisi dans Wagtail"],
        )

    def test_complet_et_details(self):
        cal = self.flux("agenda-complet")
        self.assertIn("Échange mensuel Panoramax", self.titres(cal))
        self.assertNotIn("Très ancien", self.titres(cal))  # plus de 3 mois
        evenements = {str(e["SUMMARY"]): e for e in cal.walk("VEVENT")}
        demo = evenements["Annulé : Démo BAN"]
        self.assertEqual(str(demo["STATUS"]), "CANCELLED")
        self.assertEqual(str(demo["URL"]), "http://localhost/agenda/annule-demo-ban/")
        self.assertTrue(str(demo["UID"]).startswith("evenement-"))
        self.assertEqual(str(demo["LOCATION"]), "Visio")

    def test_flux_inconnu(self):
        self.assertEqual(self.client.get("/flux/autre.ics").status_code, 404)

    def test_liens_sur_la_page_agenda(self):
        contenu = self.client.get(self.index.url).content.decode()
        self.assertIn('href="webcal://testserver/flux/agenda-fabrique.ics"', contenu)
        self.assertIn('href="webcal://testserver/flux/agenda-complet.ics"', contenu)
        self.assertIn("http://testserver/flux/agenda-fabrique.ics", contenu)
        self.assertNotIn("/agenda/ical/", contenu)
