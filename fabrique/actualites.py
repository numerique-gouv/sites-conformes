"""Écriture de la table Actus du Grist dans les pages Actualités (blog) de Sites Faciles.

- Page « Actualités » (BlogIndexPage de l'app blog) : celle dont l'adresse est
  FABRIQUE_ACTUS_SLUG (« actualites » par défaut) ; à défaut, la seule page
  Actualités du site s'il n'y en a qu'une ; sinon elle est créée.
- Une page Article (BlogEntryPage) par actu publiée dans Grist : communiqués
  rédigés dans Grist et infolettres importées de Brevo. La synchronisation
  possède le titre, la date, la description, les catégories (une par équipe),
  l'étiquette « Newsletter », l'image d'en-tête et les blocs du corps dont
  l'identifiant commence par « grist- » (chapô, texte, bouton vers la version
  web). Les autres blocs et les réglages restent aux éditeurs.
- Les catégories manquantes sont créées : l'actu remonte alors sur la fiche
  produit de l'équipe (champ « Catégorie des actualités »).
- Une page dont l'actu a été dépubliée ou supprimée dans Grist est dépubliée,
  mais reste dans Wagtail.

Une page qui a un brouillon non publié n'est pas modifiée, pour ne pas publier
par erreur le travail en cours d'un éditeur.
"""

import html
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

from django.utils.text import slugify
from wagtail.models import Locale, Page, Site

from blog.models import BlogEntryPage, BlogIndexPage, Category, CategoryEntryPage
from fabrique import grist
from fabrique.agenda import Images, _bouton, merge_owned_group
from fabrique.newsletters import SOURCE as SOURCE_NEWSLETTER
from fabrique.sync import Report, _normalize, _publish, _unique_slug

logger = logging.getLogger(__name__)

OWNED_PREFIX = "grist-"
COLLECTION_IMAGES = "Actualités"
ETIQUETTE_NEWSLETTER = "Newsletter"
# Page et vue « Actus » du document Grist, pour le lien de chaque article vers sa ligne.
PAGE_GRIST, VUE_GRIST = 4, 9

# Catégories d'actualités qui existent déjà sur le site sous un autre nom que l'équipe Grist.
CATEGORIES_EQUIPES = {
    "RNB": "referentiel-national-du-batiment",
    "BAN": "base-adresse-nationale",
    "Panoramax": "panoramax",
}


@dataclass
class Actu:
    id: int
    titre: str
    date: datetime
    equipes: list[str] = field(default_factory=list)
    source: str = ""
    chapo: str = ""
    corps: str = ""
    lien: str = ""
    image: int | None = None  # identifiant de la pièce jointe (colonne Image)

    @property
    def newsletter(self) -> bool:
        return self.source == SOURCE_NEWSLETTER


def parse(records: list[dict]) -> list[Actu]:
    """Actus publiées (case « Publié » cochée, avec un titre et une date), les plus récentes en premier."""
    actus = []
    for record in records:
        f = record.get("fields", {})
        titre, date = grist._texte(f.get("Titre")), grist._date(f.get("Date"))
        if f.get("Publie") is not True or not titre or not date:
            continue
        actus.append(
            Actu(
                id=record["id"],
                titre=titre,
                date=date,
                equipes=grist._liste(f.get("Equipe")),
                source=grist._texte(f.get("Source")),
                chapo=grist._texte(f.get("Chapo")),
                corps=grist._texte(f.get("Corps")),
                lien=grist._texte(f.get("Lien")),
                image=grist._premiere_piece_jointe(f.get("Image")),
            )
        )
    return sorted(actus, key=lambda a: (a.date, a.id), reverse=True)


@dataclass
class Source:
    """Document Grist lu : sert à fabriquer et reconnaître le lien de chaque page vers sa ligne."""

    base_url: str = grist.DEFAULT_BASE_URL
    org: str = grist.DEFAULT_ORG
    doc_id: str = grist.DEFAULT_DOC_ID

    def url(self, row_id: int) -> str:
        return f"{self.base_url.rstrip('/')}/o/{self.org}/{self.doc_id}/Actus/p/{PAGE_GRIST}#a1.s{VUE_GRIST}.r{row_id}"

    def row_id(self, page: Page) -> int | None:
        return grist.row_id_from_source_url(page.source_url, self.doc_id)


# ---------------------------------------------------------------------------
# Corps et champs de la page
# ---------------------------------------------------------------------------


def owned_blocks(actu: Actu) -> list[dict]:
    blocks = []
    if actu.chapo:
        blocks.append(
            {"type": "paragraph", "id": f"{OWNED_PREFIX}chapo", "value": f"<p><b>{html.escape(actu.chapo)}</b></p>"}
        )
    if actu.corps:
        blocks.append({"type": "markdown", "id": f"{OWNED_PREFIX}corps", "value": actu.corps})
    if actu.lien:
        texte = "Lire la newsletter" if actu.newsletter else "En savoir plus"
        bouton = _bouton("lien", texte, actu.lien, "fr-btn", "fr-icon-external-link-line")
        blocks.append(
            {"type": "buttons_list", "id": f"{OWNED_PREFIX}liens", "value": {"buttons": [bouton], "position": ""}}
        )
    return blocks


def _resume(actu: Actu, longueur: int = 160) -> str:
    """Description courte pour les moteurs de recherche et les cartes, à partir du chapô ou du texte."""
    # Jamais vide : Sites Faciles remplirait la description à l'enregistrement, et la page semblerait modifiée
    # à chaque synchronisation.
    texte = actu.chapo or re.sub(r"[#*_`>\[\]]|\(https?://[^)]*\)", "", actu.corps) or actu.titre
    texte = " ".join(texte.split())
    if len(texte) > longueur:
        texte = texte[: longueur - 1].rsplit(" ", 1)[0] + "…"
    return texte


def actu_values(actu: Actu, source: Source) -> dict:
    return {
        "title": actu.titre[:255],
        "date": actu.date,
        "search_description": _resume(actu),
        "source_url": source.url(actu.id),
    }


class Categories:
    """Catégorie du blog de chaque équipe, créée si elle n'existe pas encore."""

    def __init__(self, report: Report):
        self.report, self._cache = report, {}

    def get(self, equipe: str) -> Category:
        if equipe not in self._cache:
            slug = CATEGORIES_EQUIPES.get(equipe) or slugify(equipe)[:80]
            category = (
                Category.objects.filter(slug=slug).first() or Category.objects.filter(name__iexact=equipe).first()
            )
            if category is None:
                category = Category.objects.create(name=equipe[:80], slug=slug, locale=Locale.get_default())
                self.report.created.append(f"Catégorie {equipe}")
            self._cache[equipe] = category
        return self._cache[equipe]

    def ids(self, actu: Actu) -> list[int]:
        return sorted({self.get(e).id for e in actu.equipes})


def _categories(page: BlogEntryPage) -> list[int]:
    return sorted(lien.category_id for lien in page.entry_categories.all())


def _set_categories(page: BlogEntryPage, ids: list[int]) -> None:
    if page.pk:
        # Page existante : la révision enregistre le champ blog_categories, qui l'emporte à la publication.
        page.blog_categories = ids
    else:
        # Page pas encore enregistrée : le champ n'est pas utilisable, on passe par le modèle intermédiaire.
        page.entry_categories = [CategoryEntryPage(category_id=i) for i in ids]


def _tags(page: BlogEntryPage) -> list[str]:
    return sorted(t.name for t in page.tags.all())


# ---------------------------------------------------------------------------
# Synchronisation
# ---------------------------------------------------------------------------


def get_or_create_index(root: Page, slug: str, report: Report) -> BlogIndexPage:
    page = Page.objects.child_of(root).filter(slug=slug).specific().first()
    if isinstance(page, BlogIndexPage):
        return page
    if page is not None:
        raise RuntimeError(
            f"La page « /{slug}/ » existe mais n'est pas une page d'actualités ({page.specific_class.__name__}). "
            "Renommez-la ou indiquez une autre adresse avec FABRIQUE_ACTUS_SLUG."
        )
    existantes = list(BlogIndexPage.objects.descendant_of(root))
    if len(existantes) == 1:
        return existantes[0]
    if existantes:
        raise RuntimeError(
            "Plusieurs pages d'actualités existent sur le site : indiquez celle à utiliser avec FABRIQUE_ACTUS_SLUG "
            f"({', '.join('/' + p.slug + '/' for p in existantes)})."
        )
    index = BlogIndexPage(
        title="Actualités",
        slug=slug,
        show_in_menus=True,
        search_description="Les actualités de la Fabrique de la donnée territoriale et de ses équipes produits.",
        body=[
            {
                "type": "paragraph",
                "id": "introduction",
                "value": "<p>Les nouvelles de la Fabrique de la donnée territoriale et de ses équipes produits : "
                "communiqués, infolettres, lancements.</p>",
            }
        ],
    )
    root.add_child(instance=index)
    _publish(index)
    report.created.append(f"Page {index.title}")
    return index


def sync_actus(index: BlogIndexPage, actus: list[Actu], source: Source, report: Report, images: Images) -> None:
    pages: dict[int, BlogEntryPage] = {}
    for page in BlogEntryPage.objects.child_of(index):
        row_id = source.row_id(page)
        if row_id is not None:
            pages[row_id] = page

    categories = Categories(report)
    for actu in actus:
        page = pages.get(actu.id)
        label = actu.titre
        # Une page hors ligne a toujours des « modifications non publiées » (la dépublication en est une) :
        # seul le brouillon d'une page en ligne est le signe d'un travail en cours.
        if page is not None and page.live and page.has_unpublished_changes:
            logger.warning("%s : brouillon non publié, page laissée telle quelle.", label)
            report.skipped_drafts.append(label)
            continue

        values = actu_values(actu, source)
        values["header_image"] = images.resolve(actu, page.header_image if page is not None else None)
        category_ids = categories.ids(actu)
        tags = [ETIQUETTE_NEWSLETTER] if actu.newsletter else []
        if page is None:
            page = BlogEntryPage(slug=_unique_slug(index, slugify(actu.titre)[:80] or "actualite"), **values)
            page.body = owned_blocks(actu)
            _set_categories(page, category_ids)
            page.tags.set(tags)
            index.add_child(instance=page)
            _publish(page)
            report.created.append(label)
            continue

        stream_block = page.body.stream_block
        existing = _normalize(stream_block, list(page.body.raw_data))
        new_body = _normalize(stream_block, merge_owned_group(existing, owned_blocks(actu)))
        changed = [name for name, value in values.items() if getattr(page, name) != value]
        body_changed = new_body != existing
        categories_changed = _categories(page) != category_ids
        tags_changed = _tags(page) != tags
        if changed or body_changed or categories_changed or tags_changed or not page.live:
            for name in changed:
                setattr(page, name, values[name])
            if body_changed:
                page.body = new_body
            if categories_changed:
                _set_categories(page, category_ids)
            if tags_changed:
                page.tags.set(tags)
            _publish(page)
            report.updated.append(label)
        else:
            report.unchanged.append(label)

    publiees = {a.id for a in actus}
    for row_id, page in pages.items():
        if row_id not in publiees and page.live:
            # Décochée « Publié » ou supprimée dans Grist : la page reste dans Wagtail, hors ligne.
            page.unpublish(log_action=True)
            report.unpublished.append(page.title)


def synced_live_pages(source: Source) -> int:
    """Nombre d'articles en ligne issus de Grist (pour le garde-fou contre une table vide)."""
    return sum(1 for p in BlogEntryPage.objects.live() if source.row_id(p) is not None)


def run(
    actus: list[Actu],
    slug: str,
    source: Source | None = None,
    pieces_jointes: "grist.PiecesJointes | None" = None,
) -> Report:
    source = source or Source()
    report = Report()
    root = Site.objects.get(is_default_site=True).root_page.specific
    index = get_or_create_index(root, slug, report)
    sync_actus(index, actus, source, report, Images(pieces_jointes, source.doc_id, COLLECTION_IMAGES))
    return report
