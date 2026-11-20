"""Import des infolettres Brevo des équipes dans la table Actus du Grist.

Les équipes continuent d'envoyer leurs infolettres depuis leur compte Brevo ;
chaque infolettre arrive dans la table Actus, publiée, avec un lien vers sa
version web, puis sur le site par la synchronisation des actualités.

Seules les infolettres sont importées : pour chaque compte, on ne garde que
les campagnes envoyées dont l'objet commence par un texte donné (« Info
Panoramax ») ou dont le nom contient un texte donné (« adresse.data.gouv.fr »).
Les invitations, alertes aux utilisateurs, messages d'accueil… sont écartés.

- Une infolettre nouvelle est ajoutée au Grist, publiée, avec l'équipe du
  compte, la source « Newsletter Brevo » et l'identifiant de la campagne.
- Une infolettre déjà importée n'est plus jamais modifiée : titre, chapô,
  image, équipe et case Publié appartiennent aux éditeurs du Grist. Pour la
  retirer du site, on décoche « Publié » (une ligne supprimée serait recréée).
- Renvoi correctif : quand deux campagnes ont le même objet le même jour, seule
  la dernière est gardée ; si la première avait déjà été importée, elle est
  dépubliée.

Si un compte est illisible (clé absente ou refusée, Brevo injoignable), rien
n'est modifié pour ce compte.

Liste des comptes : variable d'environnement NEWSLETTERS_BREVO, une ligne
« Équipe | VARIABLE_DE_LA_CLE | objet: texte » ou « … | nom: texte » par compte
(séparées par des retours à la ligne ou des points-virgules). Par défaut :
Panoramax et Voies locales. Chaque clé API Brevo est dans sa propre variable
d'environnement (BREVO_CLE_PANORAMAX…).
"""

import json
import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from django.utils.text import slugify

from fabrique import grist

logger = logging.getLogger(__name__)

API_BREVO = "https://api.brevo.com/v3"
SOURCE = "Newsletter Brevo"
PARIS = ZoneInfo("Europe/Paris")
PAR_PAGE = 50
# Brevo refuse une date de fin « dans le futur » : on garde une petite marge (comme le site de la BAN).
MARGE_FIN = timedelta(minutes=5)
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


@dataclass(frozen=True)
class Compte:
    equipe: str  # valeur de la colonne Équipe, ex. « Panoramax »
    variable: str  # variable d'environnement qui contient la clé API Brevo du compte
    objet: str = ""  # garde les campagnes dont l'objet commence par ce texte…
    nom: str = ""  # … ou dont le nom contient ce texte

    def garde(self, campagne: dict) -> bool:
        objet = str(campagne.get("subject") or "").strip().casefold()
        nom = str(campagne.get("name") or "").casefold()
        if self.objet and objet.startswith(self.objet.casefold()):
            return True
        return bool(self.nom) and self.nom.casefold() in nom

    def uid(self, campagne: dict) -> str:
        # Les numéros de campagne recommencent à 1 dans chaque compte Brevo : on préfixe par l'équipe.
        return f"brevo:{slugify(self.equipe)}:{campagne['id']}"

    @property
    def filtre(self) -> str:
        return " ou ".join(
            f
            for f in (
                self.objet and f"objet commence par « {self.objet} »",
                self.nom and f"nom contient « {self.nom} »",
            )
            if f
        )


PAR_DEFAUT = [
    Compte("Panoramax", "BREVO_CLE_PANORAMAX", objet="Info Panoramax"),
    Compte("Voies locales", "BREVO_CLE_VOIES_LOCALES", objet="Info Voies locales"),
]


def depuis_env(valeur: str | None) -> list[Compte]:
    """Comptes configurés. None (variable absente) : comptes par défaut ; chaîne vide : aucun."""
    if valeur is None:
        return list(PAR_DEFAUT)
    comptes = []
    for ligne in re.split(r"[;\n]", valeur):
        if not ligne.strip():
            continue
        parties = [p.strip() for p in ligne.split("|")]
        filtre = parties[2].split(":", 1) if len(parties) == 3 else []
        cle = filtre[0].strip().casefold() if len(filtre) == 2 else ""
        texte = filtre[1].strip() if len(filtre) == 2 else ""
        if len(parties) != 3 or not parties[0] or not parties[1] or cle not in ("objet", "nom") or not texte:
            raise ValueError(
                f"NEWSLETTERS_BREVO : « {ligne.strip()} » n'est pas de la forme "
                "« Équipe | VARIABLE_DE_LA_CLE | objet: texte » ou « … | nom: texte »."
            )
        comptes.append(Compte(parties[0], parties[1], **{cle: texte}))
    return comptes


# ---------------------------------------------------------------------------
# Lecture des campagnes
# ---------------------------------------------------------------------------


def date_envoi(campagne: dict) -> datetime | None:
    valeur = str(campagne.get("sentDate") or "").strip()
    if not valeur:
        return None
    try:
        moment = datetime.fromisoformat(valeur.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def lire_campagnes(cle: str, depuis: datetime, maintenant: datetime | None = None, requete=None) -> list[dict]:
    """Campagnes envoyées depuis la date donnée, toutes pages confondues. Lève une RuntimeError si Brevo refuse."""
    requete = requete or grist._request
    fin = (maintenant or datetime.now(timezone.utc)) - MARGE_FIN
    campagnes, offset = [], 0
    while True:
        parametres = {
            "type": "classic",
            "status": "sent",
            "limit": PAR_PAGE,
            "offset": offset,
            "sort": "desc",
            "startDate": depuis.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "endDate": fin.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }
        url = f"{API_BREVO}/emailCampaigns?{urllib.parse.urlencode(parametres)}"
        reponse = json.loads(requete(url, headers={"api-key": cle, "Accept": "application/json"}) or b"{}")
        page = reponse.get("campaigns") or []
        campagnes.extend(page)
        offset += len(page)
        if not page or offset >= int(reponse.get("count") or 0):
            return campagnes


def titre(campagne: dict, envoi: datetime) -> str:
    """Objet de la campagne, complété du mois d'envoi s'il ne le contient pas déjà.

    Les équipes réutilisent souvent le même objet chaque mois (« Info Voies locales en commun ») : sans le mois,
    toutes les infolettres auraient le même titre sur le site."""
    objet = " ".join(str(campagne.get("subject") or campagne.get("name") or "").split())
    if any(mois in objet.casefold() for mois in MOIS):
        return objet
    local = envoi.astimezone(PARIS)
    return f"{objet} — {MOIS[local.month - 1]} {local.year}"


@dataclass
class Tri:
    gardees: list[dict] = field(default_factory=list)  # infolettres à importer (avec leur date d'envoi)
    remplacees: list[dict] = field(default_factory=list)  # premiers envois remplacés par un renvoi correctif
    ecartees: list[dict] = field(default_factory=list)  # autres campagnes (invitations, alertes…)


def trier(compte: Compte, campagnes: list[dict]) -> Tri:
    tri = Tri()
    retenues: dict[tuple, dict] = {}
    for campagne in campagnes:
        envoi = date_envoi(campagne)
        if envoi is None or not compte.garde(campagne):
            tri.ecartees.append(campagne)
            continue
        cle = (str(campagne.get("subject") or "").strip().casefold(), envoi.astimezone(PARIS).date())
        precedente = retenues.get(cle)
        if precedente is None:
            retenues[cle] = campagne
        elif date_envoi(precedente) < envoi:
            tri.remplacees.append(precedente)
            retenues[cle] = campagne
        else:
            tri.remplacees.append(campagne)
    tri.gardees = sorted(retenues.values(), key=date_envoi)
    return tri


# ---------------------------------------------------------------------------
# Comparaison avec le Grist
# ---------------------------------------------------------------------------


@dataclass
class Plan:
    ajouts: list[dict] = field(default_factory=list)  # champs des lignes à créer
    depublications: list[dict] = field(default_factory=list)  # {"id": …, "fields": {"Publie": False}}

    def __bool__(self):
        return bool(self.ajouts or self.depublications)


def ligne(compte: Compte, campagne: dict) -> dict:
    envoi = date_envoi(campagne)
    lien = str(campagne.get("shareLink") or "").strip()
    if not lien:
        logger.warning(
            "%s : campagne « %s » sans version web, importée non publiée.", compte.equipe, campagne.get("name")
        )
    return {
        "Titre": titre(campagne, envoi),
        "Date": envoi.timestamp(),
        "Equipe": ["L", compte.equipe],
        "Source": SOURCE,
        "Source_uid": compte.uid(campagne),
        "Publie": bool(lien),
        "Chapo": " ".join(str(campagne.get("previewText") or "").split()),
        "Lien": lien,
    }


def planifier(compte: Compte, tri: Tri, records: list[dict]) -> Plan:
    plan = Plan()
    existants = {
        r["fields"].get("Source_uid"): r
        for r in records
        if r["fields"].get("Source") == SOURCE and r["fields"].get("Source_uid")
    }
    for campagne in tri.gardees:
        if compte.uid(campagne) not in existants:
            plan.ajouts.append(ligne(compte, campagne))
    for campagne in tri.remplacees:
        record = existants.get(compte.uid(campagne))
        if record is not None and record["fields"].get("Publie"):
            plan.depublications.append({"id": record["id"], "fields": {"Publie": False}})
    return plan


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


@dataclass
class Resultat:
    compte: Compte
    tri: Tri | None = None
    plan: Plan | None = None
    erreur: str = ""

    def resume(self) -> str:
        if self.erreur:
            return f"{self.compte.equipe} : non importé ({self.erreur})"
        return (
            f"{self.compte.equipe} : {len(self.tri.gardees)} infolettres, {len(self.plan.ajouts)} ajoutées, "
            f"{len(self.plan.depublications)} dépubliées (renvoi correctif), "
            f"{len(self.tri.ecartees)} autres campagnes écartées"
        )


def importer(
    comptes: list[Compte],
    records: list[dict],
    base_url: str,
    doc_id: str,
    api_key: str,
    env: dict,
    depuis: datetime,
    ecrire: bool = True,
    requete=None,
) -> list[Resultat]:
    """Importe les infolettres de chaque compte dans le Grist. Une erreur sur un compte n'empêche pas les autres."""
    resultats = []
    for compte in comptes:
        cle = (env.get(compte.variable) or "").strip()
        if not cle:
            resultats.append(Resultat(compte, erreur=f"variable {compte.variable} absente"))
            continue
        try:
            tri = trier(compte, lire_campagnes(cle, depuis, requete=requete))
        except Exception as e:  # noqa: BLE001 — compte injoignable ou clé refusée : on passe
            logger.warning("Campagnes Brevo de %s illisibles : %s", compte.equipe, e)
            resultats.append(Resultat(compte, erreur=str(e)))
            continue
        plan = planifier(compte, tri, records)
        if ecrire and plan:
            try:
                if plan.ajouts:
                    grist.add_records(base_url, doc_id, api_key, plan.ajouts, table=grist.TABLE_ACTUS)
                if plan.depublications:
                    grist.update_records(base_url, doc_id, api_key, plan.depublications, table=grist.TABLE_ACTUS)
            except RuntimeError as e:
                logger.warning("Écriture dans Grist impossible pour %s : %s", compte.equipe, e)
                resultats.append(Resultat(compte, tri, plan, erreur=f"écriture Grist : {e}"))
                continue
        resultats.append(Resultat(compte, tri, plan))
    return resultats


def lister(resultat: Resultat) -> list[str]:
    """Une ligne par campagne lue : date, gardée ou écartée, nom et objet (option --lister)."""
    if resultat.tri is None:
        return []
    statut = {id(c): "gardée  " for c in resultat.tri.gardees}
    statut.update({id(c): "remplacée" for c in resultat.tri.remplacees})
    campagnes = resultat.tri.gardees + resultat.tri.remplacees + resultat.tri.ecartees
    campagnes.sort(key=lambda c: date_envoi(c) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    lignes = []
    for c in campagnes:
        envoi = date_envoi(c)
        jour = envoi.astimezone(PARIS).strftime("%d/%m/%Y") if envoi else "??/??/????"
        lignes.append(f"  {jour}  {statut.get(id(c), 'écartée ')}  {c.get('name', '')} — {c.get('subject', '')}")
    return lignes
