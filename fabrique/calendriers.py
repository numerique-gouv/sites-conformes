"""Import de calendriers iCal publics (Framagenda…) dans le Grist « Agenda ».

Les équipes qui tiennent déjà leur propre calendrier continuent de le faire ;
leurs événements arrivent dans la table Evenements du Grist, puis sur le site
par la synchronisation habituelle.

Pour chaque calendrier :
- un événement nouveau est ajouté au Grist, publié, avec l'équipe du calendrier
  et la source (colonne Source) ;
- un événement déjà importé est mis à jour pour les champs qui viennent du
  calendrier : titre, début, fin, lieu, lien visio, page de l'événement,
  description, annulation. Le type, l'image, la série, les inscriptions et la
  case Publié restent aux éditeurs du Grist ;
- un événement qui a disparu du calendrier est dépublié (case Publié décochée).

Si le calendrier est illisible ou vide, rien n'est modifié pour cette source.

Liste des calendriers : variable d'environnement AGENDA_CALENDRIERS, une ligne
« Source | Équipe | URL iCal » par calendrier (séparées par des retours à la
ligne ou des points-virgules). Par défaut : le Framagenda de Panoramax.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from icalendar import Calendar

from fabrique import grist

logger = logging.getLogger(__name__)

PARIS = ZoneInfo("Europe/Paris")
DUREE_PAR_DEFAUT = timedelta(hours=1)
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
# Lieux qui désignent une visio : on cherche alors le lien dans la description.
VISIO_RE = re.compile(r"\b(jitsi|visio|en ligne|zoom|teams|bbb|bigbluebutton|webinaire|webinar)\b", re.I)

# Champs du Grist qui appartiennent au calendrier d'origine (écrasés à chaque import).
CHAMPS_CALENDRIER = ("Titre", "Debut", "Fin", "Lieu", "Lien_visio", "Lien_evenement", "Description", "Annule")


@dataclass(frozen=True)
class Calendrier:
    source: str  # valeur de la colonne Source, ex. « Framagenda Panoramax »
    equipe: str  # équipe donnée aux nouveaux événements, ex. « Panoramax »
    url: str  # export iCal public


PAR_DEFAUT = [
    Calendrier(
        "Framagenda Panoramax",
        "Panoramax",
        "https://framagenda.org/remote.php/dav/public-calendars/ZQQ5s2EEwT7Nzjm5/?export",
    )
]


def depuis_env(valeur: str | None) -> list[Calendrier]:
    """Calendriers configurés. None (variable absente) : calendriers par défaut ; chaîne vide : aucun."""
    if valeur is None:
        return list(PAR_DEFAUT)
    calendriers = []
    for ligne in re.split(r"[;\n]", valeur):
        if not ligne.strip():
            continue
        parties = [p.strip() for p in ligne.split("|")]
        if len(parties) != 3 or not all(parties):
            raise ValueError(f"AGENDA_CALENDRIERS : « {ligne.strip()} » n'est pas de la forme « Source | Équipe | URL ».")
        calendriers.append(Calendrier(*parties))
    return calendriers


# ---------------------------------------------------------------------------
# Lecture du calendrier
# ---------------------------------------------------------------------------


def _moment(valeur, fin: bool = False) -> datetime:
    """datetime aware à partir d'une valeur iCal (date, datetime avec ou sans fuseau)."""
    if isinstance(valeur, datetime):
        return valeur if valeur.tzinfo else valeur.replace(tzinfo=PARIS)
    if isinstance(valeur, date):
        # Journée entière : de 0 h à 23 h 59 (la fin iCal d'une journée entière est exclusive).
        if fin:
            return datetime.combine(valeur - timedelta(days=1), time(23, 59), tzinfo=PARIS)
        return datetime.combine(valeur, time(0, 0), tzinfo=PARIS)
    raise ValueError(f"date iCal inattendue : {valeur!r}")


def _description(texte: str) -> str:
    """Texte brut iCal → markdown : chaque retour à la ligne est gardé."""
    lignes = [ligne.rstrip() for ligne in texte.strip().splitlines()]
    return "  \n".join(lignes)


def lire(contenu: bytes) -> list[dict]:
    """Événements d'un fichier iCal, sous forme de champs du Grist (+ « uid »). Ignore les événements privés."""
    calendrier = Calendar.from_ical(contenu)
    evenements = []
    for composant in calendrier.walk("VEVENT"):
        uid = str(composant.get("UID") or "").strip()
        titre = str(composant.get("SUMMARY") or "").strip()
        if not uid or not titre or "DTSTART" not in composant:
            continue
        if str(composant.get("CLASS") or "PUBLIC").upper() in ("PRIVATE", "CONFIDENTIAL"):
            continue
        if composant.get("RRULE"):
            logger.warning("« %s » est récurrent : seule la première occurrence est importée.", titre)

        debut = _moment(composant.decoded("DTSTART"))
        if "DTEND" in composant:
            fin = _moment(composant.decoded("DTEND"), fin=True)
        elif "DURATION" in composant:
            fin = debut + composant.decoded("DURATION")
        elif not isinstance(composant.decoded("DTSTART"), datetime):
            fin = _moment(composant.decoded("DTSTART") + timedelta(days=1), fin=True)
        else:
            fin = debut + DUREE_PAR_DEFAUT
        fin = max(fin, debut)

        description = str(composant.get("DESCRIPTION") or "")
        lieu = str(composant.get("LOCATION") or "").strip()
        lien_visio = ""
        if URL_RE.fullmatch(lieu):
            lien_visio, lieu = lieu, ""
        elif lieu and VISIO_RE.search(lieu) and URL_RE.search(description):
            lien_visio, lieu = URL_RE.search(description).group(0), ""

        evenements.append(
            {
                "uid": uid,
                "Titre": titre,
                "Debut": debut.timestamp(),
                "Fin": fin.timestamp(),
                "Lieu": lieu,
                "Lien_visio": lien_visio,
                "Lien_evenement": str(composant.get("URL") or "").strip(),
                "Description": _description(description),
                "Annule": str(composant.get("STATUS") or "").upper() == "CANCELLED",
            }
        )
    return evenements


# ---------------------------------------------------------------------------
# Comparaison avec le Grist
# ---------------------------------------------------------------------------


@dataclass
class Plan:
    ajouts: list[dict] = field(default_factory=list)  # champs des lignes à créer
    mises_a_jour: list[dict] = field(default_factory=list)  # {"id": …, "fields": {…}}
    depublications: list[dict] = field(default_factory=list)  # {"id": …, "fields": {"Publie": False}}

    def __bool__(self):
        return bool(self.ajouts or self.mises_a_jour or self.depublications)


def _egal(champ: str, actuel, nouveau) -> bool:
    if champ in ("Debut", "Fin"):
        return isinstance(actuel, (int, float)) and abs(actuel - nouveau) < 1
    if champ == "Annule":
        return bool(actuel) == nouveau
    return (actuel or "") == nouveau


def planifier(calendrier: Calendrier, evenements: list[dict], records: list[dict]) -> Plan:
    plan = Plan()
    existants = {
        r["fields"].get("Source_uid"): r
        for r in records
        if r["fields"].get("Source") == calendrier.source and r["fields"].get("Source_uid")
    }
    vus = set()
    for ev in evenements:
        uid = ev["uid"]
        if uid in vus:
            continue
        vus.add(uid)
        champs = {k: ev[k] for k in CHAMPS_CALENDRIER}
        record = existants.get(uid)
        if record is None:
            plan.ajouts.append(
                {
                    **champs,
                    "Source": calendrier.source,
                    "Source_uid": uid,
                    "Equipe": ["L", calendrier.equipe],
                    "Publie": True,
                }
            )
            continue
        differences = {k: v for k, v in champs.items() if not _egal(k, record["fields"].get(k), v)}
        if differences:
            plan.mises_a_jour.append({"id": record["id"], "fields": differences})

    if evenements:  # calendrier vide : on ne dépublie rien (garde-fou)
        for uid, record in existants.items():
            if uid not in vus and record["fields"].get("Publie"):
                plan.depublications.append({"id": record["id"], "fields": {"Publie": False}})
    return plan


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


@dataclass
class Resultat:
    calendrier: Calendrier
    plan: Plan | None = None
    erreur: str = ""

    def resume(self) -> str:
        if self.erreur:
            return f"{self.calendrier.source} : non importé ({self.erreur})"
        p = self.plan
        return (
            f"{self.calendrier.source} : {len(p.ajouts)} ajoutés, {len(p.mises_a_jour)} mis à jour, "
            f"{len(p.depublications)} dépubliés"
        )


def importer(
    calendriers: list[Calendrier],
    records: list[dict],
    base_url: str,
    doc_id: str,
    api_key: str,
    ecrire: bool = True,
) -> list[Resultat]:
    """Importe chaque calendrier dans le Grist. Une erreur sur un calendrier n'empêche pas les autres."""
    resultats = []
    for calendrier in calendriers:
        try:
            evenements = lire(grist._get(calendrier.url))
        except Exception as e:  # noqa: BLE001 — calendrier injoignable ou illisible : on passe
            logger.warning("Calendrier %s illisible : %s", calendrier.source, e)
            resultats.append(Resultat(calendrier, erreur=str(e)))
            continue
        plan = planifier(calendrier, evenements, records)
        if ecrire and plan:
            try:
                if plan.ajouts:
                    grist.add_records(base_url, doc_id, api_key, plan.ajouts)
                if plan.mises_a_jour or plan.depublications:
                    grist.update_records(base_url, doc_id, api_key, plan.mises_a_jour + plan.depublications)
            except RuntimeError as e:
                logger.warning("Écriture dans Grist impossible pour %s : %s", calendrier.source, e)
                resultats.append(Resultat(calendrier, plan, erreur=f"écriture Grist : {e}"))
                continue
        resultats.append(Resultat(calendrier, plan))
    return resultats
