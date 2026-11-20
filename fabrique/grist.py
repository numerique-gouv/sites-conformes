"""Lecture de l'agenda de la Fabrique dans Grist.

Le document « Agenda » (grist.numerique.gouv.fr, espace fab-donnee-territoriale)
contient une table Evenements, sur le modèle de l'agenda du site mode produit :
mêmes identifiants de colonnes, mêmes colonnes calculées (État, Lien
d'inscription, Ajouter à Outlook…). Le document est privé : on le lit avec une
clé API Grist (variable d'environnement GRIST_API_KEY).
"""

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://grist.numerique.gouv.fr"
DEFAULT_ORG = "fab-donnee-territoriale"
DEFAULT_DOC_ID = "habcH4ftoLRf"
TABLE = "Evenements"
TABLE_ACTUS = "Actus"

# Durée retenue quand la fin n'est pas renseignée (même règle que le lien Outlook calculé dans Grist).
DUREE_PAR_DEFAUT = timedelta(hours=1)


@dataclass
class Evenement:
    id: int
    titre: str
    debut: datetime
    fin: datetime
    lieu: str = ""
    lien_visio: str = ""
    lien_evenement: str = ""
    description: str = ""
    public: str = ""
    type: str = ""
    equipes: list[str] = field(default_factory=list)
    series: list[str] = field(default_factory=list)
    annule: bool = False
    complet: bool = False
    etat: str = ""
    lien_inscription: str = ""
    places_restantes: int | None = None
    lien_outlook: str = ""
    image: int | None = None  # identifiant de la pièce jointe (colonne Image)

    @property
    def etiquettes(self) -> list[str]:
        """Type, équipes et séries, sans doublon, dans cet ordre."""
        vues, resultat = set(), []
        for valeur in [self.type, *self.equipes, *self.series]:
            if valeur and valeur.casefold() not in vues:
                vues.add(valeur.casefold())
                resultat.append(valeur)
        return resultat


def _texte(valeur) -> str:
    return valeur.strip() if isinstance(valeur, str) else ""


def _liste(valeur) -> list[str]:
    """Colonne « liste de choix » : Grist renvoie ["L", "a", "b"]."""
    if isinstance(valeur, list):
        return [v.strip() for v in valeur[1:] if isinstance(v, str) and v.strip()]
    texte = _texte(valeur)
    return [texte] if texte else []


def _date(valeur) -> datetime | None:
    # Colonne Date/DateTime : Grist renvoie un horodatage Unix (secondes, UTC).
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        return datetime.fromtimestamp(valeur, tz=timezone.utc)
    return None


def _entier(valeur) -> int | None:
    return valeur if isinstance(valeur, int) and not isinstance(valeur, bool) else None


def _premiere_piece_jointe(valeur) -> int | None:
    """Colonne « pièces jointes » : Grist renvoie ["L", id1, id2…]. On garde la première."""
    if isinstance(valeur, list):
        return next((_entier(v) for v in valeur[1:] if _entier(v) is not None), None)
    return None


def parse(records: list[dict]) -> list[Evenement]:
    """Événements publiés (case « Publié » cochée, avec un titre et une date de début), triés par date."""
    evenements = []
    for record in records:
        f = record.get("fields", {})
        titre, debut = _texte(f.get("Titre")), _date(f.get("Debut"))
        if f.get("Publie") is not True or not titre or not debut:
            continue
        fin = _date(f.get("Fin"))
        if not fin or fin < debut:
            fin = debut + DUREE_PAR_DEFAUT
        evenements.append(
            Evenement(
                id=record["id"],
                titre=titre,
                debut=debut,
                fin=fin,
                lieu=_texte(f.get("Lieu")),
                lien_visio=_texte(f.get("Lien_visio")),
                lien_evenement=_texte(f.get("Lien_evenement")),
                description=_texte(f.get("Description")),
                public=_texte(f.get("Public")),
                type=_texte(f.get("Type")),
                equipes=_liste(f.get("Equipe")),
                series=_liste(f.get("Serie")),
                annule=f.get("Annule") is True,
                complet=f.get("Complet") is True,
                etat=_texte(f.get("Etat")),
                lien_inscription=_texte(f.get("Lien_inscription")),
                places_restantes=_entier(f.get("Places_restantes")),
                lien_outlook=_texte(f.get("Ajouter_outlook")),
                image=_premiere_piece_jointe(f.get("Image")),
            )
        )
    return sorted(evenements, key=lambda e: (e.debut, e.id))


def _request(
    url: str,
    api_key: str | None = None,
    method: str = "GET",
    payload: dict | None = None,
    timeout: int = 60,
    attempts: int = 3,
    headers: dict | None = None,
) -> bytes:
    """Corps de la réponse. Lève une RuntimeError après les essais.

    Sans clé, la requête est anonyme (calendrier iCal public). Un ajout (POST) n'est jamais retenté, pour ne
    pas créer de doublons si la première requête a abouti malgré l'erreur."""
    headers = {"User-Agent": "fabrique-site-facile/sync", **(headers or {})}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    if method == "POST":
        attempts = 1
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (URL https configurée)
                return response.read()
        except urllib.error.HTTPError as e:
            last_error = e
            # Clé refusée, document ou table introuvable : inutile de réessayer. Le message du service
            # (« Key not found », « unrecognised IP address »…) dit pourquoi ; il ne contient pas la clé.
            if e.code < 500 and e.code != 429:
                try:
                    detail = " ".join(e.read(300).decode("utf-8", "replace").split())
                except Exception:  # noqa: BLE001
                    detail = ""
                if detail:
                    last_error = RuntimeError(f"{e} — {detail}")
                break
        except Exception as e:  # noqa: BLE001
            last_error = e
        logger.warning("%s %s impossible (essai %s/%s) : %s", method, url, attempt + 1, attempts, last_error)
        if attempt + 1 < attempts:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"{method} {url} impossible : {last_error}")


def _get(url: str, api_key: str | None = None) -> bytes:
    return _request(url, api_key)


def _api(base_url: str, doc_id: str) -> str:
    return f"{base_url.rstrip('/')}/api/docs/{doc_id}"


def fetch_records(base_url: str, doc_id: str, api_key: str, table: str = TABLE) -> list[dict]:
    """Toutes les lignes de la table (Evenements par défaut). Lève une erreur si le document est illisible."""
    return json.loads(_get(f"{_api(base_url, doc_id)}/tables/{table}/records", api_key))["records"]


def add_records(
    base_url: str, doc_id: str, api_key: str, fields: list[dict], lot: int = 100, table: str = TABLE
) -> None:
    """Ajoute des lignes à la table (Evenements par défaut), par lots."""
    url = f"{_api(base_url, doc_id)}/tables/{table}/records"
    for i in range(0, len(fields), lot):
        _request(url, api_key, "POST", {"records": [{"fields": f} for f in fields[i : i + lot]]})


def update_records(
    base_url: str, doc_id: str, api_key: str, records: list[dict], lot: int = 100, table: str = TABLE
) -> None:
    """Modifie des lignes de la table (Evenements par défaut) : [{"id": …, "fields": {…}}, …], par lots."""
    url = f"{_api(base_url, doc_id)}/tables/{table}/records"
    for i in range(0, len(records), lot):
        _request(url, api_key, "PATCH", {"records": records[i : i + lot]})


class PiecesJointes:
    """Accès aux pièces jointes du document (images des événements).

    La liste (nom et taille des fichiers) est lue une fois, à la première image demandée ; un fichier n'est
    téléchargé que s'il n'a pas déjà été importé dans Wagtail."""

    def __init__(self, base_url: str, doc_id: str, api_key: str):
        self.base_url, self.doc_id, self.api_key = base_url, doc_id, api_key
        self._infos: dict[int, dict] | None = None

    def infos(self, attachment_id: int) -> dict | None:
        """{"fileName": …, "fileSize": …} de la pièce jointe, ou None si elle n'existe plus."""
        if self._infos is None:
            records = json.loads(_get(f"{_api(self.base_url, self.doc_id)}/attachments", self.api_key))["records"]
            self._infos = {r["id"]: r.get("fields", {}) for r in records}
        return self._infos.get(attachment_id)

    def download(self, attachment_id: int) -> bytes:
        return _get(f"{_api(self.base_url, self.doc_id)}/attachments/{attachment_id}/download", self.api_key)


def source_url(base_url: str, org: str, doc_id: str, row_id: int) -> str:
    """Lien vers la ligne dans Grist, gardé dans la page Wagtail pour la retrouver à la synchronisation suivante."""
    return f"{base_url.rstrip('/')}/o/{org}/{doc_id}/Agenda/p/1#a1.s1.r{row_id}"


def row_id_from_source_url(url: str | None, doc_id: str) -> int | None:
    """Identifiant de ligne Grist d'une page synchronisée, ou None pour une page créée à la main."""
    if not url or f"/{doc_id}/" not in url or ".r" not in url:
        return None
    suffix = url.rsplit(".r", 1)[1]
    return int(suffix) if suffix.isdigit() else None
