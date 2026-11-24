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
- un événement à venir qui a disparu du calendrier est dépublié (case Publié
  décochée). Un événement passé n'est jamais dépublié : certains flux (les
  sites Sites Faciles, par exemple) ne contiennent que les événements à venir.

Si le calendrier est illisible ou vide, rien n'est modifié pour cette source.

Trois formats de source : iCal (Framagenda, sites Sites Faciles…), l'API JSON
des événements de la BAN (bal-admin.adresse.data.gouv.fr/api/events), qui donne
aussi le public visé (colonne Public, suivie comme les autres champs) et le type
(donné à la création seulement), et le Grist de la BAN (table Evenements, mêmes
champs, plus des adresses et une case de validation de publication ; lu avec la
clé GRIST_API_KEY, qui doit y avoir accès).

Liste des calendriers : variable d'environnement AGENDA_CALENDRIERS, une ligne
« Source | Équipe | URL [| format] » par calendrier
(format : ical par défaut, ban ou grist-ban) (séparées par des retours à la
ligne ou des points-virgules). Par défaut : le Framagenda de Panoramax, l'agenda
du site Voies locales en commun, et les deux agendas de la BAN (API et Grist).
"""

import json
import logging
import re
import time as horloge
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
# Champs suivis seulement quand la source les fournit (l'API BAN donne le public visé).
CHAMPS_FACULTATIFS = ("Public",)
# Liens de visioconférence (sinon, un lien de source va dans « Page de l'événement »).
VISIO_URL_RE = re.compile(
    r"webinaire\.numerique\.gouv\.fr|visio\.|jit\.si|jitsi|zoom\.us|teams\.microsoft|bbb|bigbluebutton", re.I
)


@dataclass(frozen=True)
class Calendrier:
    source: str  # valeur de la colonne Source, ex. « Framagenda Panoramax »
    equipe: str  # équipe donnée aux nouveaux événements, ex. « Panoramax »
    url: str  # export iCal public, ou API JSON
    format: str = "ical"  # « ical » ou « ban » (API des événements de la BAN)


PAR_DEFAUT = [
    Calendrier(
        "Framagenda Panoramax",
        "Panoramax",
        "https://framagenda.org/remote.php/dav/public-calendars/ZQQ5s2EEwT7Nzjm5/?export",
    ),
    # Site Sites Faciles : le flux iCal ne contient que les événements à venir.
    Calendrier(
        "Site Voies locales",
        "Voies locales",
        "https://www.voies-locales.beta.gouv.fr/actualit%C3%A9s/ical/",
    ),
    # API JSON de l'agenda de la BAN (webinaires Mes Adresses, événements partenaires) : tout l'historique.
    Calendrier(
        "Agenda BAN",
        "BAN",
        "https://bal-admin.adresse.data.gouv.fr/api/events",
        "ban",
    ),
    # Grist de la BAN (Adresse-Lab, rencontres régionales…) : événements validés pour publication.
    Calendrier(
        "Grist BAN",
        "BAN",
        "https://grist.numerique.gouv.fr/api/docs/cS36SuWF2W2z",
        "grist-ban",
    ),
]

FORMATS = ("ical", "ban", "grist-ban")


def depuis_env(valeur: str | None) -> list[Calendrier]:
    """Calendriers configurés. None (variable absente) : calendriers par défaut ; chaîne vide : aucun."""
    if valeur is None:
        return list(PAR_DEFAUT)
    calendriers = []
    for ligne in re.split(r"[;\n]", valeur):
        if not ligne.strip():
            continue
        parties = [p.strip() for p in ligne.split("|")]
        if len(parties) not in (3, 4) or not all(parties) or (len(parties) == 4 and parties[3] not in FORMATS):
            raise ValueError(
                f"AGENDA_CALENDRIERS : « {ligne.strip()} » n'est pas de la forme "
                "« Source | Équipe | URL [| ical ou ban] »."
            )
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


# Types de la BAN → types du Grist (donnés à la création seulement).
TYPES_BAN = {
    "formation": "Formation",
    "formation-lvl2": "Formation",
    "formation spéciale": "Formation",
    "partenaire": "Rencontre communauté",
    "adresselab": "Atelier",
    "adresse-region": "Rencontre communauté",
}
# Séries des types de la BAN (données à la création seulement).
SERIES_BAN = {"adresselab": "Adresse-Lab"}


def _heure_ban(jour: date, heure) -> datetime | None:
    try:
        h, m = (int(x) for x in str(heure).split(":")[:2])
    except (TypeError, ValueError):
        return None
    return datetime.combine(jour, time(h, m), tzinfo=PARIS)


def _adresse_ban(adresse) -> str:
    if isinstance(adresse, str):
        return adresse.strip()
    if isinstance(adresse, dict):
        parties = [str(v).strip() for v in adresse.values() if isinstance(v, (str, int)) and str(v).strip()]
        return ", ".join(parties)
    return ""


def _creation_ban(type_ban: str) -> dict:
    creation = {"Type": TYPES_BAN.get(type_ban, "")}
    if type_ban in SERIES_BAN:
        creation["Serie"] = ["L", SERIES_BAN[type_ban]]
    return creation


def lire_ban(contenu: bytes) -> list[dict]:
    """Événements de l'API de la BAN (liste JSON), sous forme de champs du Grist (+ « uid », « creation »)."""
    evenements = []
    for item in json.loads(contenu):
        if not isinstance(item, dict):
            continue
        uid, titre = str(item.get("id") or "").strip(), str(item.get("title") or "").strip()
        try:
            jour = date.fromisoformat(str(item.get("date") or "")[:10])
        except ValueError:
            continue
        if not uid or not titre:
            continue
        debut = _heure_ban(jour, item.get("startHour")) or datetime.combine(jour, time(0, 0), tzinfo=PARIS)
        fin = _heure_ban(jour, item.get("endHour"))
        if fin is None or fin < debut:
            fin = debut + DUREE_PAR_DEFAUT if item.get("startHour") else _moment(jour + timedelta(days=1), fin=True)

        lien = str(item.get("href") or "").strip()
        lien_visio = lien if lien and VISIO_URL_RE.search(lien) else ""
        sous_titre = str(item.get("subtitle") or "").strip()
        description = str(item.get("description") or "").strip()
        texte = "\n\n".join(p for p in (f"**{sous_titre}**" if sous_titre else "", _description(description)) if p)

        evenements.append(
            {
                "uid": uid,
                "Titre": titre,
                "Debut": debut.timestamp(),
                "Fin": fin.timestamp(),
                "Lieu": "" if item.get("isOnlineOnly") else _adresse_ban(item.get("address")),
                "Lien_visio": lien_visio,
                "Lien_evenement": "" if lien_visio else lien,
                "Description": texte,
                "Annule": False,
                "Public": str(item.get("target") or "").strip(),
                "creation": _creation_ban(str(item.get("type") or "").strip().lower()),
            }
        )
    return evenements


def _date_grist(valeur) -> str:
    """Colonne Date de Grist (horodatage à minuit UTC) → « AAAA-MM-JJ »."""
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        return datetime.fromtimestamp(valeur, tz=ZoneInfo("UTC")).date().isoformat()
    return ""


def lire_grist_ban(url_document: str, api_key: str) -> list[dict]:
    """Événements validés du Grist de la BAN, ramenés au format de l'API pour réutiliser lire_ban."""
    lignes = json.loads(grist._get(f"{url_document}/tables/Evenements/records", api_key))["records"]
    adresses = {
        r["id"]: r.get("fields", {})
        for r in json.loads(grist._get(f"{url_document}/tables/Adresses_Evenements/records", api_key))["records"]
    }
    items = []
    for ligne in lignes:
        f = ligne.get("fields", {})
        if f.get("validation_publication") is not True:
            continue
        adresse = adresses.get(f.get("address")) if f.get("address") else None
        if adresse:
            rue = " ".join(str(adresse.get(k) or "").strip() for k in ("numero", "voie")).strip()
            ville = " ".join(str(adresse.get(k) or "").strip() for k in ("codePostal", "commune")).strip()
            adresse = ", ".join(p for p in (str(adresse.get("nom") or "").strip(), rue, ville) if p)
        items.append(
            {
                "id": f"grist-{ligne['id']}",
                "title": f.get("title"),
                "subtitle": f.get("subtitle"),
                "description": f.get("description"),
                "type": f.get("type"),
                "target": f.get("target"),
                "date": _date_grist(f.get("date")),
                "isOnlineOnly": f.get("isOnlineOnly"),
                "address": adresse,
                "href": f.get("href"),
                "startHour": f.get("startHour"),
                "endHour": f.get("endHour"),
            }
        )
    return lire_ban(json.dumps(items).encode())


LECTEURS = {"ical": lambda contenu: lire(contenu), "ban": lambda contenu: lire_ban(contenu)}


def charger(calendrier: Calendrier, api_key: str) -> list[dict]:
    """Événements d'une source, quel que soit son format."""
    if calendrier.format == "grist-ban":
        return lire_grist_ban(calendrier.url.rstrip("/"), api_key)
    return LECTEURS[calendrier.format](grist._get(calendrier.url))


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


def _passe(fields: dict, maintenant: float) -> bool:
    fin = fields.get("Fin") or fields.get("Debut")
    return isinstance(fin, (int, float)) and fin < maintenant


def planifier(
    calendrier: Calendrier, evenements: list[dict], records: list[dict], maintenant: float | None = None
) -> Plan:
    maintenant = horloge.time() if maintenant is None else maintenant
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
        champs.update({k: ev[k] for k in CHAMPS_FACULTATIFS if k in ev})
        record = existants.get(uid)
        if record is None:
            plan.ajouts.append(
                {
                    **{k: v for k, v in ev.get("creation", {}).items() if v},
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
            fields = record["fields"]
            # Un événement passé qui sort du flux reste publié (archives de l'agenda).
            if uid not in vus and fields.get("Publie") and not _passe(fields, maintenant):
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
            evenements = charger(calendrier, api_key)
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
