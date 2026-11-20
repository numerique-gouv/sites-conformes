"""Conversion du HTML d'une infolettre (e-mail Brevo) en Markdown pour le site.

Un e-mail est une mise en page en tableaux, avec des styles « Outlook », des
pixels de suivi, un en-tête (logo, accroche, titre) et un pied (réseaux sociaux,
désinscription). On n'en garde que le contenu : intertitres, paragraphes, gras
et italique, listes, liens et images. Le résultat va dans la colonne Corps du
Grist, où il peut être retouché, puis s'affiche sur le site avec les styles
DSFR, comme un article ordinaire.
"""

import re
import unicodedata

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

IGNORES = {"head", "style", "script", "title", "meta", "link", "noscript", "svg", "button", "form", "input"}
BLOCS = {
    "p", "div", "td", "th", "tr", "table", "tbody", "thead", "tfoot", "section", "article", "center", "body",
    "header", "footer", "main", "blockquote", "hr", "html",
}  # fmt: skip
TITRES = {"h1": 2, "h2": 2, "h3": 3, "h4": 4, "h5": 4, "h6": 4}
INVISIBLES = dict.fromkeys(map(ord, "­​‌‍⁠﻿͏"), None)
GABARIT = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)  # balises Brevo : {{ mirror }}, {{ contact.PRENOM }}…
LIEN_TECHNIQUE = re.compile(r"^\{\{|unsubscribe|desinscri|désinscri|mirror|preferences|/optout", re.I)
RESEAUX = re.compile(r"social[-_]?icons|facebook|twitter|linkedin|instagram|youtube|mastodon|bluesky", re.I)
LIGNE_TECHNIQUE = re.compile(
    r"version en ligne|afficher (dans|ce message dans) (le|votre) navigateur|voir (cet e-?mail|ce message) dans", re.I
)
PIED = re.compile(
    r"désinscri|desinscri|désabonn|desabonn|unsubscribe|ne (plus|souhaitez plus) recevoir|vous (recevez|avez reçu) "
    r"(cet|ce|cette)|cet e-?mail a été envoyé|ce message a été envoyé|gérer (vos|mes) (préférences|abonnements)",
    re.I,
)
MOIS = "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre"
TAILLE_MIN = 60  # en pixels : logos d'en-tête, icônes et pixels de suivi en dessous


def _texte(chaine: str) -> str:
    chaine = unicodedata.normalize("NFC", chaine.translate(INVISIBLES)).replace("\xa0", " ")
    # Balise devant une virgule ou un point : on retire aussi l'espace
    # (« Bonjour {{ contact.PRENOM }}, » → « Bonjour, »).
    chaine = re.sub(r"\s*\{\{[^}]*\}\}\s*(?=[,.])", "", chaine)
    return re.sub(r"\s+", " ", GABARIT.sub("", chaine))


def _echapper(chaine: str) -> str:
    return chaine.replace("*", "\\*")


def _cache(tag: Tag) -> bool:
    style = re.sub(r"\s", "", str(tag.get("style") or "")).lower()
    classes = " ".join(tag.get("class") or []).lower()
    return "display:none" in style or "mso-hide:all" in style or "preheader" in classes


def _pixels(valeur) -> int | None:
    match = re.match(r"\s*(\d+)", str(valeur or ""))
    return int(match.group(1)) if match else None


def _dimension(img: Tag, nom: str) -> int | None:
    direct = _pixels(img.get(nom))
    if direct is not None:
        return direct
    match = re.search(rf"(?:^|;)\s*{nom}\s*:\s*(\d+)px", str(img.get("style") or ""), re.I)
    return int(match.group(1)) if match else None


def _image(img: Tag) -> str:
    src = str(img.get("src") or "").strip()
    if not src.startswith(("http://", "https://")):
        return ""
    largeur, hauteur = _dimension(img, "width"), _dimension(img, "height")
    if (largeur is not None and largeur <= 2) or (hauteur is not None and hauteur <= 2):
        return ""  # pixel de suivi
    if (largeur is not None and largeur <= TAILLE_MIN) or (hauteur is not None and hauteur <= TAILLE_MIN // 2):
        return ""  # logo, icône de réseau social, séparateur
    if RESEAUX.search(src) or RESEAUX.search(str(img.get("alt") or "")):
        return ""
    alt = _texte(str(img.get("alt") or "")).strip().replace("[", "").replace("]", "")
    return f"![{alt}]({src.replace(' ', '%20')})"


class _Sortie:
    def __init__(self):
        self.blocs: list[str] = []
        self.ligne: list[str] = []

    def couper(self):
        texte = re.sub(r"[ \t]+", " ", "".join(self.ligne)).strip()
        if texte:
            self.blocs.append(texte)
        self.ligne = []

    def tout(self) -> str:
        self.couper()
        return " ".join(self.blocs)


def _en_ligne(noeud: Tag) -> str:
    """Contenu d'un élément sur une seule ligne (les blocs intérieurs sont mis bout à bout).

    Les espaces au début et à la fin sont conservés : « <b>avril&nbsp;</b>et » doit donner « **avril** et »."""
    sortie = _Sortie()
    for enfant in noeud.children:
        _rendre(enfant, sortie)
    if not sortie.blocs:
        return re.sub(r"[ \t]+", " ", "".join(sortie.ligne))
    return sortie.tout()


def _bords(texte: str) -> tuple[str, str, str]:
    coeur = texte.strip()
    if not coeur:
        return texte, "", ""
    return texte[: len(texte) - len(texte.lstrip())], coeur, texte[len(texte.rstrip()) :]


def _entourer(texte: str, marque: str) -> str:
    debut, coeur, fin = _bords(texte)
    if not coeur or coeur.startswith("!["):
        return texte
    return f"{debut}{marque}{coeur}{marque}{fin}"


def _gras(tag: Tag) -> bool:
    style = re.sub(r"\s", "", str(tag.get("style") or "")).lower()
    return tag.name in ("strong", "b") or "font-weight:bold" in style or re.search(r"font-weight:[6-9]00", style)


def _rendre(noeud, sortie: _Sortie) -> None:
    if isinstance(noeud, Comment):
        return
    if isinstance(noeud, NavigableString):
        sortie.ligne.append(_echapper(_texte(str(noeud))))
        return
    if not isinstance(noeud, Tag) or noeud.name in IGNORES or _cache(noeud):
        return
    nom = noeud.name
    if nom == "img":
        sortie.ligne.append(_image(noeud))
    elif nom == "br":
        sortie.couper()
    elif nom == "a":
        href = str(noeud.get("href") or "").strip()
        debut, contenu, fin = _bords(_en_ligne(noeud))
        if LIEN_TECHNIQUE.search(href) or not contenu:
            sortie.ligne.append(debut)
            return
        if href.startswith(("http://", "https://", "mailto:")):
            contenu = f"[{contenu}]({href.replace(' ', '%20')})"
        sortie.ligne.append(f"{debut}{contenu}{fin}")
    elif nom in TITRES:
        sortie.couper()
        texte = _en_ligne(noeud).replace("**", "").strip()
        if texte:
            sortie.blocs.append("#" * TITRES[nom] + " " + texte)
    elif nom in ("ul", "ol"):
        sortie.couper()
        elements = [re.sub(r"\s+", " ", _en_ligne(li)).strip() for li in noeud.find_all("li", recursive=False)]
        elements = [e for e in elements if e]
        if elements:
            puces = [f"{i}. " if nom == "ol" else "- " for i in range(1, len(elements) + 1)]
            sortie.blocs.append("\n".join(p + e for p, e in zip(puces, elements)))
    elif nom in BLOCS or nom == "li":
        sortie.couper()
        for enfant in noeud.children:
            _rendre(enfant, sortie)
        sortie.couper()
    elif _gras(noeud):
        sortie.ligne.append(_entourer(_en_ligne(noeud), "**"))
    elif nom in ("em", "i"):
        sortie.ligne.append(_entourer(_en_ligne(noeud), "*"))
    else:
        for enfant in noeud.children:
            _rendre(enfant, sortie)


def _comparable(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte.casefold())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in texte if not unicodedata.combining(c))).strip()


def _nettoyer_titre(bloc: str) -> str:
    """« ## \\[ 🚀 Visio Fondation \\] » → « ## 🚀 Visio Fondation »."""
    if not bloc.startswith("#"):
        return bloc
    diese, _, texte = bloc.partition(" ")
    texte = re.sub(r"^\s*[\[\(]\s*|\s*[\]\)]\s*$", "", texte.strip())
    return f"{diese} {texte}" if texte else ""


def _sans_entete(blocs: list[str], titre: str) -> list[str]:
    """Retire l'en-tête de l'e-mail (logo, accroche, titre et date) quand il reprend le titre de l'actu."""
    cible = _comparable(re.sub(rf"\b({MOIS})\b|\d{{4}}|—.*$", "", titre, flags=re.I))
    if not cible:
        return blocs
    for i, bloc in enumerate(blocs[:12]):
        texte = _comparable(re.sub(r"^#+\s*", "", bloc).replace("*", ""))
        if bloc.startswith("#") and texte and (texte.startswith(cible) or cible.startswith(texte)):
            reste = blocs[i + 1 :]
            # Date de l'infolettre juste sous le titre (« Avril 2026 »).
            if reste and len(reste[0]) <= 40 and re.search(rf"\b({MOIS})\b|\b20\d\d\b", reste[0], re.I):
                reste = reste[1:]
            return reste
    return blocs


def _decoratif(bloc: str) -> bool:
    """Bloc de pied d'e-mail : image seule (logo, icône), adresse postale, e-mail de contact…"""
    sans_images = re.sub(r"\[?!\[[^\]]*\]\([^)]*\)(\]\([^)]*\))?", "", bloc).strip()
    if not sans_images:
        return True
    if "](http" in sans_images:
        return False  # un lien vers une page : du contenu (ressources, liens utiles…)
    texte = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", sans_images).replace("*", "").strip()
    return len(texte) <= 60 and not re.search(r"[.!?…:]$", texte) and not bloc.startswith(("#", "- ", "1. "))


def _sans_pied(blocs: list[str]) -> list[str]:
    """Coupe le pied de l'e-mail : à partir de la mention de désinscription (cherchée dans la seconde moitié),
    puis les logos, icônes et coordonnées qui la précèdent."""
    for i in range(len(blocs) // 2, len(blocs)):
        if PIED.search(blocs[i]):
            blocs = blocs[:i]
            while blocs and _decoratif(blocs[-1]):
                blocs.pop()
            return blocs
    return blocs


def en_markdown(html: str, titre: str = "") -> str:
    """Markdown du contenu de l'infolettre, sans en-tête ni pied. Chaîne vide si rien d'exploitable."""
    if not html or not html.strip():
        return ""
    soupe = BeautifulSoup(html, "html.parser")
    sortie = _Sortie()
    _rendre(soupe.body or soupe, sortie)
    sortie.couper()
    blocs = []
    for bloc in sortie.blocs:
        bloc = _nettoyer_titre(bloc.strip())
        texte = re.sub(r"[\s*_#>\-|]", "", bloc)
        if not texte or LIGNE_TECHNIQUE.search(bloc):
            continue
        if blocs and blocs[-1] == bloc:
            continue
        blocs.append(bloc)
    blocs = _sans_pied(_sans_entete(blocs, titre))
    # Un intertitre sans rien dessous (fin coupée) n'a pas de sens.
    while blocs and blocs[-1].startswith("#"):
        blocs.pop()
    # Deux passages en gras collés (« **a****b** ») : on les fusionne, comme dans l'e-mail.
    return "\n\n".join(blocs).replace("****", "").strip()
