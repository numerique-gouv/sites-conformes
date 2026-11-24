"""Mise à jour de la page d'accueil pour y intégrer les pages Produits, Agenda et Actualités.

Le contenu de l'accueil se saisit dans Wagtail : cette commande n'en réécrit rien, elle y ajoute ou complète des
éléments repérés par leur texte. On peut la relancer sans créer de doublons.

- Bandeau : boutons « Découvrir nos produits » et « Voir l'agenda ». Ils vont dans les boutons de l'en-tête si la
  page en affiche un, sinon dans un bloc « Liste de boutons » placé juste après le bloc d'introduction.
- Avant la section « Comment ça marche ? » : deux blocs « Prochains rendez-vous » (agenda) et « Dernières
  actualités ». Le gabarit de ces blocs (templates/content_manager/blocks/) est celui des cartes de l'agenda et des
  actualités, avec le lien d'abonnement iCal sous les rendez-vous.
- Encart des projets sélectionnés par le comité des partenaires : lien vers le dernier compte rendu du comité.
- Gouvernance (Collectif vigie, Comité des partenaires, Comités d'investissement) : un lien sous chaque
  description, vers l'agenda filtré sur le type d'événement ou vers le compte rendu du comité.
- Menu principal (sur demande seulement) : Produits, Agenda et Actualités juste après Accueil.

Les blocs ajoutés ont un identifiant qui commence par « accueil- » ; ils sont mis à jour sur place si on relance la
commande. Les liens ajoutés dans les textes sont reconnus par leur adresse.

Par défaut, le résultat est enregistré comme brouillon : on le prévisualise dans Wagtail puis on publie.
"""

from __future__ import annotations

import copy
import html
import logging
import re
import uuid
from dataclasses import dataclass, field
from urllib.parse import quote

from django.utils.text import slugify
from wagtail.models import Page, Site

from blog.models import BlogEntryPage, BlogIndexPage
from content_manager.models import Tag
from events.models import EventsIndexPage
from fabrique.models import ProduitsIndexPage

logger = logging.getLogger(__name__)

PREFIXE = "accueil-"

# Textes repérés sur la page d'accueil (comparés sans accents typographiques ni casse).
ANCRE_COMMENT = "comment ça marche"
ANCRE_INTRO = ("espace de coopération", "opérée par l'ign", "opéré par l'ign")
ENCART_AVANT = "ces sujets vous intéressent"
ENCART_APRES = "nouveaux chantiers"
GOUVERNANCE = {
    "collectif_vigie": "se réunit régulièrement",
    "comite_partenaires": "le comité des partenaires rassemble",
    "comites_investissement": "organise tous les six mois",
}
TAGS = {"collectif_vigie": "Collectif vigie", "comites_investissement": "Comité d'investissement"}
MENU = ["produits", "agenda", "actualites", "partenaires", "equipe"]


@dataclass
class Rapport:
    faits: list[str] = field(default_factory=list)
    ignores: list[str] = field(default_factory=list)

    def fait(self, message: str) -> None:
        self.faits.append(message)

    def ignore(self, message: str) -> None:
        logger.warning(message)
        self.ignores.append(message)


@dataclass
class Pages:
    accueil: Page
    produits: ProduitsIndexPage | None
    agenda: EventsIndexPage | None
    actualites: BlogIndexPage | None
    compte_rendu: BlogEntryPage | None

    @classmethod
    def trouver(cls, accueil: Page) -> Pages:
        def premiere(model):
            return model.objects.descendant_of(accueil).live().first()

        compte_rendu = (
            BlogEntryPage.objects.descendant_of(accueil)
            .live()
            .filter(title__icontains="comité des partenaires")
            .order_by("-date")
            .first()
        )
        return cls(
            accueil, premiere(ProduitsIndexPage), premiere(EventsIndexPage), premiere(BlogIndexPage), compte_rendu
        )


# ---------------------------------------------------------------------------
# Texte
# ---------------------------------------------------------------------------


def normaliser(texte: str) -> str:
    texte = html.unescape(re.sub(r"<[^>]+>", " ", texte))
    texte = texte.replace("’", "'").replace("\xa0", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", texte).strip().casefold()


def contient(valeur, aiguille: str) -> bool:
    """Vrai si le texte d'un bloc brut (dictionnaires, listes, chaînes imbriqués) contient « aiguille »."""
    if isinstance(valeur, str):
        return aiguille in normaliser(valeur)
    if isinstance(valeur, dict):
        return any(contient(v, aiguille) for v in valeur.values())
    if isinstance(valeur, list):
        return any(contient(v, aiguille) for v in valeur)
    return False


PARAGRAPHE = re.compile(r"<(p|ul|ol)\b[^>]*>.*?</\1>", re.S)
TITRE = re.compile(r"<h[1-6]\b", re.I)


def inserer_paragraphe(texte: str, aiguille: str, ajout: str, avant: bool = False) -> str | None:
    """Insère « ajout » après la fin de la sous-section (jusqu'au titre suivant) où se trouve « aiguille »,
    ou juste avant le paragraphe qui la contient si « avant ». None si le texte ne la contient pas."""
    for m in PARAGRAPHE.finditer(texte):
        if aiguille not in normaliser(m.group(0)):
            continue
        if avant:
            return texte[: m.start()] + ajout + texte[m.start() :]
        suivant = TITRE.search(texte, m.end())
        fin = suivant.start() if suivant else len(texte)
        # Recule avant les espaces de fin, pour coller l'ajout au dernier paragraphe de la sous-section.
        while fin > m.end() and texte[fin - 1].isspace():
            fin -= 1
        return texte[:fin] + ajout + texte[fin:]
    return None


def lien_html(texte: str, *, page: Page | None = None, href: str = "") -> str:
    if page is not None:
        return f'<p><a linktype="page" id="{page.id}">{html.escape(texte, quote=False)}</a></p>'
    return f'<p><a href="{html.escape(href)}">{html.escape(texte, quote=False)}</a></p>'


def deja_present(texte: str, *, page: Page | None = None, href: str = "") -> bool:
    if page is not None:
        return re.search(rf'linktype="page"[^>]*\bid="{page.id}"', texte) is not None
    return f'href="{html.escape(href)}"' in texte


def ajouter_lien(blocs: list[dict], aiguille: str, texte_lien: str, avant: bool = False, **cible) -> str:
    """Ajoute un lien dans le premier texte riche des blocs qui contient « aiguille ».
    Renvoie « ajouté », « présent » ou « introuvable »."""

    def parcourir(valeur, poser):
        if isinstance(valeur, str):
            if "<" not in valeur or aiguille not in normaliser(valeur):
                return None
            if deja_present(valeur, **cible):
                return "présent"
            nouveau = inserer_paragraphe(valeur, aiguille, lien_html(texte_lien, **cible), avant=avant)
            if nouveau is None:
                return None
            poser(nouveau)
            return "ajouté"
        if isinstance(valeur, dict):
            for cle in list(valeur):
                resultat = parcourir(valeur[cle], lambda v, c=cle: valeur.__setitem__(c, v))
                if resultat:
                    return resultat
        if isinstance(valeur, list):
            for i in range(len(valeur)):
                resultat = parcourir(valeur[i], lambda v, i=i: valeur.__setitem__(i, v))
                if resultat:
                    return resultat
        return None

    return parcourir(blocs, None) or "introuvable"


# ---------------------------------------------------------------------------
# Blocs
# ---------------------------------------------------------------------------


def bouton(texte: str, page: Page, type_: str) -> dict:
    return {
        "type": "button",
        "id": str(uuid.uuid4()),
        "value": {
            "page": page.id,
            "document": None,
            "external_url": "",
            "text": texte,
            "button_type": type_,
            "icon_class": "",
            "icon_side": "",
        },
    }


def boutons_bandeau(pages: Pages, primaire_pris: bool) -> list[dict]:
    resultat = []
    if pages.produits:
        resultat.append(
            bouton("Découvrir nos produits", pages.produits, "fr-btn fr-btn--secondary" if primaire_pris else "fr-btn")
        )
    if pages.agenda:
        resultat.append(bouton("Voir l'agenda", pages.agenda, "fr-btn fr-btn--secondary"))
    return resultat


def bloc_agenda(pages: Pages) -> dict:
    return {
        "type": "events_recent_entries",
        "id": f"{PREFIXE}agenda",
        "value": {
            "title": "Prochains rendez-vous",
            "heading_tag": "h2",
            "index_page": pages.agenda.id,
            "entries_count": 4,
            "category_filter": None,
            "tag_filter": None,
            "author_filter": None,
            "source_filter": None,
            "show_filters": False,
        },
    }


def bloc_actualites(pages: Pages) -> dict:
    return {
        "type": "blog_recent_entries",
        "id": f"{PREFIXE}actualites",
        "value": {
            "title": "Dernières actualités",
            "heading_tag": "h2",
            "blog": pages.actualites.id,
            "entries_count": 4,
            "category_filter": None,
            "tag_filter": None,
            "author_filter": None,
            "source_filter": None,
            "show_filters": False,
        },
    }


def placer(blocs: list[dict], bloc: dict, index: int) -> str:
    """Remplace le bloc de même identifiant s'il existe, sinon l'insère à « index »."""
    for i, existant in enumerate(blocs):
        if existant.get("id") == bloc["id"]:
            blocs[i] = bloc
            return "mis à jour"
    blocs.insert(index, bloc)
    return "ajouté"


def index_de(blocs: list[dict], aiguille: str) -> int | None:
    for i, bloc in enumerate(blocs):
        if not str(bloc.get("id", "")).startswith(PREFIXE) and contient(bloc.get("value"), aiguille):
            return i
    return None


# ---------------------------------------------------------------------------
# Étapes
# ---------------------------------------------------------------------------


def etape_bandeau(page: Page, blocs: list[dict], pages: Pages, rapport: Rapport) -> list[dict] | None:
    """Boutons du bandeau. Renvoie la nouvelle valeur brute de header_cta_buttons, ou None si inchangée."""
    a_un_en_tete = bool(page.header_image_id or page.header_color_class) and bool(
        page.header_with_title or page.header_cta_text or page.header_cta_buttons
    )
    if a_un_en_tete:
        entete = list(page.header_cta_buttons.raw_data) if page.header_cta_buttons else []
        existants = entete[0]["value"] if entete else []
        cibles = {b["value"].get("page") for b in existants}
        primaire_pris = any(b["value"].get("button_type") in ("fr-btn", "", None) for b in existants)
        nouveaux = [b for b in boutons_bandeau(pages, primaire_pris) if b["value"]["page"] not in cibles]
        if not nouveaux:
            rapport.fait("Bandeau : boutons déjà présents dans l'en-tête")
            return None
        if entete:
            entete[0] = {**entete[0], "value": existants + nouveaux}
        else:
            entete = [{"type": "buttons", "id": str(uuid.uuid4()), "value": nouveaux}]
        rapport.fait(f"Bandeau : {len(nouveaux)} bouton(s) ajouté(s) dans l'en-tête")
        return entete

    position = next((i for a in ANCRE_INTRO if (i := index_de(blocs[:3], a)) is not None), None)
    if position is None:
        position = 0
        rapport.ignore("Bandeau : bloc d'introduction non reconnu, boutons placés après le premier bloc")
    valeur = {"buttons": boutons_bandeau(pages, primaire_pris=False), "position": ""}
    existant = next((b for b in blocs if b.get("id") == f"{PREFIXE}boutons"), None)
    if existant:
        # On garde les identifiants des boutons pour ne pas créer de différence à chaque passage.
        for ancien, nouveau in zip(existant["value"].get("buttons", []), valeur["buttons"]):
            nouveau["id"] = ancien.get("id", nouveau["id"])
    etat = placer(blocs, {"type": "buttons_list", "id": f"{PREFIXE}boutons", "value": valeur}, position + 1)
    rapport.fait(f"Bandeau : liste de boutons {etat} après le bloc d'introduction")
    return None


def etape_agenda_actualites(blocs: list[dict], pages: Pages, rapport: Rapport) -> None:
    position = index_de(blocs, ANCRE_COMMENT)
    if position is None:
        position = len(blocs)
        rapport.ignore("Section « Comment ça marche ? » introuvable : agenda et actualités ajoutés en fin de page")
    for nom, page, fabrique in (
        ("Prochains rendez-vous", pages.agenda, bloc_agenda),
        ("Dernières actualités", pages.actualites, bloc_actualites),
    ):
        if page is None:
            rapport.ignore(f"{nom} : page d'index introuvable, bloc non ajouté")
            continue
        etat = placer(blocs, fabrique(pages), position)
        if etat == "ajouté":
            position += 1
        else:
            position = next(i for i, b in enumerate(blocs) if b["id"] == fabrique(pages)["id"]) + 1
        rapport.fait(f"{nom} : bloc {etat}")


def etape_encart(blocs: list[dict], pages: Pages, rapport: Rapport) -> None:
    if pages.compte_rendu is None:
        rapport.ignore("Encart du comité : aucun compte rendu du comité des partenaires dans les actualités")
        return
    texte = "Lire le compte rendu du comité des partenaires"
    etat = ajouter_lien(blocs, ENCART_AVANT, texte, avant=True, page=pages.compte_rendu)
    if etat == "introuvable":
        etat = ajouter_lien(blocs, ENCART_APRES, texte, page=pages.compte_rendu)
    if etat == "introuvable":
        rapport.ignore("Encart du comité : texte de l'encart introuvable")
    else:
        rapport.fait(f"Encart du comité : lien vers « {pages.compte_rendu.title} » {etat}")


def url_agenda_filtre(pages: Pages, nom_tag: str) -> str | None:
    if pages.agenda is None:
        return None
    tag = Tag.objects.filter(name__iexact=nom_tag).first() or Tag.objects.filter(slug=slugify(nom_tag)).first()
    if tag is None:
        return None
    return f"{pages.agenda.url}?tag={quote(tag.slug)}"


def etape_gouvernance(blocs: list[dict], pages: Pages, rapport: Rapport) -> None:
    liens = {
        "collectif_vigie": (
            "Les prochains collectifs vigie dans l'agenda",
            url_agenda_filtre(pages, TAGS["collectif_vigie"]),
        ),
        "comites_investissement": (
            "Les prochains comités d'investissement dans l'agenda",
            url_agenda_filtre(pages, TAGS["comites_investissement"]),
        ),
    }
    for cle, aiguille in GOUVERNANCE.items():
        if cle == "comite_partenaires":
            if pages.compte_rendu is None:
                rapport.ignore("Comité des partenaires : aucun compte rendu à lier")
                continue
            texte, cible = "Lire le dernier compte rendu", {"page": pages.compte_rendu}
        else:
            texte, href = liens[cle]
            if href is None:
                rapport.ignore(f"{texte} : étiquette « {TAGS[cle]} » ou page Agenda introuvable")
                continue
            cible = {"href": href}
        etat = ajouter_lien(blocs, aiguille, texte, **cible)
        if etat == "introuvable":
            rapport.ignore(
                f"Gouvernance : texte « {aiguille} » introuvable dans un texte riche, lien « {texte} » non ajouté"
            )
        else:
            rapport.fait(f"Gouvernance : lien « {texte} » {etat}")


def mettre_a_jour_menu(site: Site, rapport: Rapport, simulation: bool = False) -> None:
    from wagtailmenus.models import MainMenu

    menu = MainMenu.get_for_site(site)
    items = list(menu.get_menu_items_manager().all().select_related("link_page"))
    if not items:
        rapport.ignore("Menu : aucun élément dans le menu principal")
        return

    def rang(item):
        slug = slugify(item.link_page.slug if item.link_page else (item.link_text or ""))
        if item.link_page_id == site.root_page_id:
            return -1
        for i, debut in enumerate(MENU):
            if slug.startswith(debut) or (debut == "actualites" and slug.startswith("les-actualites")):
                return i
        return len(MENU)

    ordonnes = sorted(items, key=lambda it: (rang(it), it.sort_order))
    avant = [it.menu_text for it in items]
    apres = [it.menu_text for it in ordonnes]
    if avant == apres:
        rapport.fait("Menu : ordre déjà à jour")
        return
    if not simulation:
        for i, item in enumerate(ordonnes):
            if item.sort_order != i:
                item.sort_order = i
                item.save(update_fields=["sort_order"])
    rapport.fait(f"Menu : {' · '.join(avant)} → {' · '.join(apres)}")


def run(publier: bool = False, menu: bool = False, simulation: bool = False) -> Rapport:
    rapport = Rapport()
    site = Site.objects.get(is_default_site=True)
    page = site.root_page.specific
    if not hasattr(page, "body"):
        raise ValueError(f"La page d'accueil « {page.title} » n'a pas de corps modifiable")
    if page.has_unpublished_changes:
        raise ValueError(
            f"La page d'accueil « {page.title} » a un brouillon non publié : "
            "publiez-le ou supprimez-le avant de relancer"
        )

    pages = Pages.trouver(page)
    stream = page.body.stream_block
    avant = list(stream.get_prep_value(page.body))
    blocs = copy.deepcopy(avant)

    entete = etape_bandeau(page, blocs, pages, rapport)
    etape_agenda_actualites(blocs, pages, rapport)
    etape_encart(blocs, pages, rapport)
    etape_gouvernance(blocs, pages, rapport)
    if menu:
        mettre_a_jour_menu(site, rapport, simulation=simulation)

    apres = list(stream.get_prep_value(stream.to_python(blocs)))
    if apres == avant and entete is None:
        rapport.fait("Page d'accueil : rien à changer")
        return rapport
    if simulation:
        return rapport

    page.body = apres
    if entete is not None:
        page.header_cta_buttons = entete
    revision = page.save_revision(log_action=True)
    if publier:
        revision.publish()
        rapport.fait(f"Page d'accueil « {page.title} » publiée")
    else:
        rapport.fait(
            f"Page d'accueil « {page.title} » : brouillon enregistré, à prévisualiser et publier dans Wagtail"
        )
    return rapport
