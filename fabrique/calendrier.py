"""Vue calendrier (mois) de la page Agenda.

La page Agenda de Sites Faciles (events.EventsIndexPage) affiche une liste de cartes. On y ajoute une vue
calendrier, affichée par défaut ; la liste reste accessible avec ?vue=liste.

- ?mois=AAAA-MM choisit le mois (par défaut : le mois en cours, ou celui de la date de début filtrée) ;
- les filtres de Sites Faciles par étiquette et par catégorie s'appliquent aussi au calendrier ;
- chaque événement est coloré d'après son équipe (étiquettes lues dans Grist, fabrique.EtiquettesEvenement) ;
- au-delà de MAX_PAR_JOUR événements, la case propose « + N autres », vers la liste de ce jour.
"""

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from django.http import QueryDict
from django.utils import timezone

from events.models import EventEntryPage

MAX_PAR_JOUR = 3
MOIS = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]
JOURS = [("Lun", "lundi"), ("Mar", "mardi"), ("Mer", "mercredi"), ("Jeu", "jeudi"), ("Ven", "vendredi"),
         ("Sam", "samedi"), ("Dim", "dimanche")]  # fmt: skip

# Couleur par équipe (classe CSS fabrique-cal--…), par ordre de priorité quand un événement a plusieurs équipes :
# les équipes produits avant la Fabrique, comme pour les logos dans le Grist.
EQUIPES = [
    ("Panoramax", "panoramax"),
    ("RNB", "rnb"),
    ("BAN", "ban"),
    ("Voies locales", "voies-locales"),
    ("Fabrique de la donnée territoriale", "fabrique"),
]


@dataclass
class Case:
    titre: str
    url: str
    heure: str  # « 14h », « 9h30 », ou vide (journée entière, jour suivant d'un événement sur plusieurs jours)
    equipe: str  # nom de l'équipe retenue pour la couleur, ou vide
    couleur: str  # suffixe de la classe CSS
    annule: bool


@dataclass
class Jour:
    date: date
    dans_le_mois: bool
    aujourdhui: bool
    cases: list[Case] = field(default_factory=list)
    autres: int = 0
    url_autres: str = ""

    @property
    def libelle(self) -> str:
        return f"{JOURS[self.date.weekday()][1]} {self.date.day} {MOIS[self.date.month - 1]}"


def url_avec(request, **params) -> str:
    """Adresse de la page courante avec les paramètres donnés (None : retiré), sans le numéro de page."""
    query: QueryDict = request.GET.copy()
    query.pop("page", None)
    for cle, valeur in params.items():
        if valeur is None:
            query.pop(cle, None)
        else:
            query[cle] = valeur
    chaine = query.urlencode()
    return f"{request.path}?{chaine}" if chaine else request.path


def mois_affiche(request, aujourdhui: date) -> date:
    """Premier jour du mois à afficher."""
    for valeur in (request.GET.get("mois", ""), request.GET.get("date_from", "")[:7]):
        try:
            return datetime.strptime(valeur, "%Y-%m").date().replace(day=1)
        except ValueError:
            continue
    return aujourdhui.replace(day=1)


def _heure(moment: datetime) -> str:
    return f"{moment.hour}h{moment.minute:02d}" if moment.minute else f"{moment.hour}h"


def _equipe(page) -> tuple[str, str]:
    etiquettes = getattr(page, "etiquettes_grist", None)
    equipes = set(etiquettes.equipes) if etiquettes else set()
    for nom, couleur in EQUIPES:
        if nom in equipes:
            return nom, couleur
    return "", "autre"


def evenements(index, request, debut: date, fin: date):
    """Événements en ligne de l'agenda qui touchent la période [debut, fin], filtres de la page appliqués."""
    qs = (
        EventEntryPage.objects.descendant_of(index)
        .live()
        .filter(event_date_start__date__lte=fin, event_date_end__date__gte=debut)
        .order_by("event_date_start")
        .select_related("etiquettes_grist")
    )
    if request.GET.get("tag"):
        qs = qs.filter(tags__slug=request.GET["tag"])
    if request.GET.get("category"):
        qs = qs.filter(event_categories__slug=request.GET["category"])
    return qs.distinct()


def construire(index, request, aujourdhui: date | None = None) -> dict:
    """Contexte du gabarit fabrique/agenda/calendrier.html."""
    aujourdhui = aujourdhui or timezone.localdate()
    premier = mois_affiche(request, aujourdhui)
    nb_jours = calendar.monthrange(premier.year, premier.month)[1]
    dernier = premier.replace(day=nb_jours)
    debut_grille = premier - timedelta(days=premier.weekday())
    fin_grille = dernier + timedelta(days=6 - dernier.weekday())

    jours = {}
    d = debut_grille
    while d <= fin_grille:
        jours[d] = Jour(d, d.month == premier.month, d == aujourdhui)
        d += timedelta(days=1)

    equipes_presentes = {}
    for page in evenements(index, request, premier, dernier):
        debut = timezone.localtime(page.event_date_start)
        fin = timezone.localtime(page.event_date_end) if page.event_date_end else debut
        nom_equipe, couleur = _equipe(page)
        if nom_equipe:
            equipes_presentes[nom_equipe] = couleur
        journee_entiere = (debut.hour, debut.minute) == (0, 0)
        jour = max(debut.date(), premier)
        while jour <= min(fin.date(), dernier):
            heure = _heure(debut) if jour == debut.date() and not journee_entiere else ""
            jours[jour].cases.append(
                Case(
                    titre=page.title,
                    url=page.url,
                    heure=heure,
                    equipe=nom_equipe,
                    couleur=couleur,
                    annule=page.title.startswith("Annulé : "),
                )
            )
            jour += timedelta(days=1)

    for jour in jours.values():
        if len(jour.cases) > MAX_PAR_JOUR:
            jour.autres = len(jour.cases) - (MAX_PAR_JOUR - 1)
            jour.cases = jour.cases[: MAX_PAR_JOUR - 1]
            iso = jour.date.isoformat()
            jour.url_autres = url_avec(request, vue="liste", mois=None, date_from=iso, date_to=iso)

    liste_jours = list(jours.values())
    precedent = (premier - timedelta(days=1)).replace(day=1)
    suivant = dernier + timedelta(days=1)
    return {
        "titre_mois": f"{MOIS[premier.month - 1].capitalize()} {premier.year}",
        "entetes": JOURS,
        "semaines": [liste_jours[i : i + 7] for i in range(0, len(liste_jours), 7)],
        "jours_du_mois_avec_evenements": [j for j in liste_jours if j.dans_le_mois and (j.cases or j.autres)],
        "url_precedent": url_avec(request, mois=precedent.strftime("%Y-%m"), date_from=None, date_to=None),
        "url_suivant": url_avec(request, mois=suivant.strftime("%Y-%m"), date_from=None, date_to=None),
        "titre_precedent": f"{MOIS[precedent.month - 1]} {precedent.year}",
        "titre_suivant": f"{MOIS[suivant.month - 1]} {suivant.year}",
        "url_aujourdhui": url_avec(request, mois=None, date_from=None, date_to=None)
        if premier != aujourdhui.replace(day=1)
        else "",
        "legende": [(nom, couleur) for nom, couleur in EQUIPES if nom in equipes_presentes],
    }
