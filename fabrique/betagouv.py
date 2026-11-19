"""Lecture des fiches produits et membres de beta.gouv.fr.

L'API publique de beta.gouv.fr (https://beta.gouv.fr/api/v2.6/) est générée
à partir du dépôt GitHub betagouv/beta.gouv.fr : startups.json reprend les
fiches content/_startups/*.md et authors.json les fiches content/_authors/*.md.
On la lit plutôt que le dépôt pour n'avoir que deux requêtes à faire.
"""

import json
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://beta.gouv.fr/api/v2.6"
STARTUP_PAGE_URL = "https://beta.gouv.fr/startups/{id}.html"

# Phases beta.gouv.fr : libellé affiché, couleur du badge DSFR, ordre d'affichage.
PHASES = {
    "investigation": ("En investigation", "new", 1),
    "construction": ("En construction", "info", 2),
    "acceleration": ("En accélération", "purple-glycine", 3),
    "consolidation": ("En consolidation", "green-menthe", 4),
    "transfere": ("Pérennisé", "success", 5),
    "success": ("Pérennisé", "success", 5),
    "alumni": ("Pérennisé", "success", 5),
}
# Toute phase absente de PHASES dont le nom commence par ceci sort du site.
INACTIVE_PHASE_PREFIXES = ("abandon",)


@dataclass
class Member:
    id: str
    fullname: str
    role: str
    employer: str


@dataclass
class Product:
    id: str
    name: str
    pitch: str
    link: str
    repository: str
    contact: str
    phase: str
    markdown: str
    sponsors: list[str] = field(default_factory=list)
    members: list[Member] = field(default_factory=list)

    @property
    def source_url(self) -> str:
        return STARTUP_PAGE_URL.format(id=self.id)

    @property
    def phase_label(self) -> str:
        return PHASES.get(self.phase, (self.phase, "", 99))[0]

    @property
    def phase_color(self) -> str:
        return PHASES.get(self.phase, ("", "grey", 99))[1]

    @property
    def phase_order(self) -> int:
        return PHASES.get(self.phase, ("", "", 99))[2]

    @property
    def short_name(self) -> str:
        """Nom court pour les étiquettes : « RNB, le Référentiel… » → « RNB »."""
        name = self.name
        for sep in (",", " - ", " – ", " ("):
            name = name.split(sep)[0]
        return name.strip()


def fetch_json(url: str, timeout: int = 120, attempts: int = 3):
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "fabrique-site-facile/sync"})
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (URL fixe en https)
                return json.load(response)
        except Exception as e:  # noqa: BLE001
            last_error = e
            logger.warning("Lecture de %s impossible (essai %s/%s) : %s", url, attempt + 1, attempts, e)
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Lecture de {url} impossible : {last_error}")


def normalize_name(name: str) -> str:
    """Remet en casse normale les mots saisis tout en majuscules (« Nicolas KOKLA » → « Nicolas Kokla »)."""

    def fix(word: str) -> str:
        if len(word) > 1 and word.isupper():
            return "-".join(part.capitalize() for part in word.split("-"))
        return word

    return " ".join(fix(w) for w in name.split())


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _current_phase(phases: list[dict]) -> str:
    dated = [p for p in phases if p.get("name")]
    if not dated:
        return ""
    dated.sort(key=lambda p: str(p.get("start") or ""))
    return dated[-1]["name"]


def is_active_phase(phase: str) -> bool:
    if phase in PHASES:
        return True
    return bool(phase) and not phase.startswith(INACTIVE_PHASE_PREFIXES)


def parse(startups_json: dict, authors_json: list, incubator: str, today: date) -> tuple[list[Product], set[str]]:
    """Renvoie (produits actifs de l'incubateur avec leurs membres actuels, identifiants des produits inactifs)."""
    products: dict[str, Product] = {}
    inactive: set[str] = set()

    for item in startups_json.get("data", []):
        rel = (item.get("relationships") or {}).get("incubator") or {}
        if (rel.get("data") or {}).get("id") != incubator:
            continue
        attrs = item.get("attributes") or {}
        phase = _current_phase(attrs.get("phases") or [])
        if not is_active_phase(phase):
            inactive.add(item["id"])
            continue
        products[item["id"]] = Product(
            id=item["id"],
            name=(attrs.get("name") or item["id"]).strip(),
            pitch=(attrs.get("pitch") or "").strip(),
            link=(attrs.get("link") or "").strip(),
            repository=(attrs.get("repository") or "").strip(),
            contact=(attrs.get("contact") or "").strip(),
            phase=phase,
            markdown=urllib.parse.unquote(attrs.get("content_url_encoded_markdown") or "").strip(),
            sponsors=[s.rstrip("/").split("/")[-1].upper() for s in attrs.get("sponsors") or [] if s],
        )

    for author in authors_json:
        for mission in author.get("missions") or []:
            start, end = _parse_date(mission.get("start")), _parse_date(mission.get("end"))
            if (start and start > today) or (end and end < today):
                continue
            for startup_id in mission.get("startups") or []:
                product = products.get(startup_id)
                if not product or any(m.id == author["id"] for m in product.members):
                    continue
                product.members.append(
                    Member(
                        id=author["id"],
                        fullname=normalize_name(author.get("fullname") or author["id"]),
                        role=(author.get("role") or "").strip(),
                        employer=(mission.get("employer") or "").strip(),
                    )
                )

    for product in products.values():
        product.members.sort(key=lambda m: m.fullname.split()[-1].lower() if m.fullname else m.id)

    ordered = sorted(products.values(), key=lambda p: (p.phase_order, p.name.lower()))
    return ordered, inactive


def load(api_base: str, incubator: str, today: date) -> tuple[list[Product], set[str]]:
    startups = fetch_json(f"{api_base.rstrip('/')}/startups.json")
    authors = fetch_json(f"{api_base.rstrip('/')}/authors.json")
    return parse(startups, authors, incubator, today)
