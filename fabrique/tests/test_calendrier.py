from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.test import RequestFactory, TestCase
from django.utils.text import slugify
from wagtail.models import Site

from events.models import EventEntryPage, EventsIndexPage
from fabrique import calendrier
from fabrique.models import EtiquettesEvenement

PARIS = ZoneInfo("Europe/Paris")


def moment(*args):
    return datetime(*args, tzinfo=PARIS)


class CalendrierTests(TestCase):
    def setUp(self):
        root = Site.objects.get(is_default_site=True).root_page
        self.index = EventsIndexPage(title="Agenda", slug="agenda")
        root.add_child(instance=self.index)
        self.index.save_revision().publish()

    def evenement(self, titre, debut, fin, equipes=(), tags=()):
        page = EventEntryPage(title=titre, slug=slugify(titre), event_date_start=debut, event_date_end=fin)
        page.tags.set(list(tags))
        self.index.add_child(instance=page)
        page.save_revision().publish()
        if equipes:
            EtiquettesEvenement.objects.create(page=page, equipes=list(equipes))
        return page

    def get(self, params=""):
        reponse = self.client.get(self.index.url + params)
        self.assertEqual(reponse.status_code, 200)
        return reponse.content.decode()

    def test_vue_calendrier_par_defaut(self):
        self.evenement("Démo RNB", moment(2027, 3, 9, 14), moment(2027, 3, 9, 15), equipes=["RNB"])
        self.evenement("Atelier BAN", moment(2027, 3, 9, 9, 30), moment(2027, 3, 9, 11), equipes=["BAN", "RNB"])
        self.evenement("Salon", moment(2027, 3, 30), moment(2027, 4, 2, 23, 59), equipes=["Panoramax"])
        self.evenement("Annulé : Webinaire", moment(2027, 3, 12, 10), moment(2027, 3, 12, 11))
        contenu = self.get("?mois=2027-03")

        self.assertIn("Événements de Mars 2027", contenu)
        self.assertIn('aria-current="page">Calendrier</a>', contenu)
        self.assertNotIn("fr-card__title", contenu)  # pas de cartes en vue calendrier
        # Heure et couleur de l'équipe ; avec plusieurs équipes, priorité Panoramax, RNB, BAN, Voies locales, Fabrique.
        self.assertRegex(contenu, r'fabrique-cal--rnb"\s+href="/agenda/demo-rnb/"')
        self.assertIn('<span class="fabrique-cal__heure">14h</span> Démo RNB', contenu)
        self.assertIn('<span class="fabrique-cal__heure">9h30</span> Atelier BAN', contenu)
        self.assertRegex(contenu, r'fabrique-cal--rnb"\s+href="/agenda/atelier-ban/"')
        # Événement sur plusieurs jours : chaque jour du mois (30 et 31 mars), sans heure (journée entière).
        self.assertEqual(contenu.count('href="/agenda/salon/"'), 2 * 2)  # grille + liste mobile
        self.assertIn("fabrique-cal--annule", contenu)
        self.assertIn("fabrique-cal--autre", contenu)
        # Légende : seulement les équipes présentes ce mois-ci.
        self.assertIn("Panoramax</li>", contenu)
        self.assertNotIn("Voies locales</li>", contenu)
        # Navigation entre les mois.
        self.assertIn('href="/agenda/?mois=2027-02#posts-list"', contenu)
        self.assertIn('href="/agenda/?mois=2027-04#posts-list"', contenu)
        self.assertIn("Revenir au mois en cours", contenu)

        avril = self.get("?mois=2027-04")
        self.assertEqual(avril.count('href="/agenda/salon/"'), 2 * 2)  # 1er et 2 avril
        self.assertNotIn("Démo RNB", avril)

    def test_jour_charge(self):
        for i in range(5):
            self.evenement(f"Réunion {i}", moment(2027, 3, 15, 9 + i), moment(2027, 3, 15, 10 + i))
        contenu = self.get("?mois=2027-03")
        self.assertIn("Réunion 1", contenu)
        self.assertNotIn("Réunion 2", contenu)
        self.assertIn("+ 3 autres", contenu)
        self.assertIn("/agenda/?vue=liste&amp;date_from=2027-03-15&amp;date_to=2027-03-15#posts-list", contenu)

    def test_vue_liste_et_filtre(self):
        self.evenement("Démo RNB", moment(2027, 3, 9, 14), moment(2027, 3, 9, 15), tags=["RNB"])
        self.evenement("Atelier BAN", moment(2027, 3, 10, 14), moment(2027, 3, 10, 15), tags=["BAN"])
        liste = self.get("?vue=liste")
        self.assertIn('aria-current="page">Liste</a>', liste)
        self.assertIn("fr-card__title", liste)
        self.assertNotIn("fabrique-calendrier__grille", liste)

        filtre = self.get("?mois=2027-03&tag=rnb")
        self.assertIn("Démo RNB", filtre)
        self.assertNotIn("Atelier BAN", filtre)
        # La bascule garde le filtre.
        self.assertIn('href="/agenda/?tag=rnb&amp;vue=liste#posts-list"', filtre)

    def test_archives_sans_calendrier(self):
        self.evenement("Ancien", moment(2020, 1, 9, 14), moment(2020, 1, 9, 15))
        contenu = self.client.get(self.index.url + "archives/").content.decode()
        self.assertNotIn("fabrique-bascule", contenu)
        self.assertNotIn("fabrique-calendrier", contenu.split("</head>")[1])
        self.assertIn("Ancien", contenu)

    def test_mois_par_defaut_et_aujourdhui(self):
        requete = RequestFactory().get("/agenda/", {"mois": "pas-une-date"})
        contexte = calendrier.construire(self.index, requete, aujourdhui=date(2027, 3, 18))
        self.assertEqual(contexte["titre_mois"], "Mars 2027")
        jours = [j for s in contexte["semaines"] for j in s]
        self.assertEqual([j.date for j in jours if j.aujourdhui], [date(2027, 3, 18)])
        self.assertEqual(jours[0].date, date(2027, 3, 1))  # mars 2027 commence un lundi
        self.assertEqual(contexte["url_aujourdhui"], "")

        requete = RequestFactory().get("/agenda/", {"date_from": "2027-06-12"})
        self.assertEqual(calendrier.construire(self.index, requete, date(2027, 3, 18))["titre_mois"], "Juin 2027")
