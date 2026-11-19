"""Écriture des produits et des équipes beta.gouv.fr dans les pages Wagtail.

- Catalogue « Produits » (ProduitsIndexPage), créé s'il n'existe pas.
- Une fiche (ProduitPage) par produit actif. La synchronisation possède tous
  ses champs beta.gouv.fr (mission, phase, liens, équipe, capture…) mais jamais
  le corps de la page, l'image d'en-tête ni les réglages, qui restent aux éditeurs.
- Page Équipe : section « Les équipes produits ». Sur cette page éditoriale, la
  synchronisation ne possède que les blocs dont l'identifiant commence par
  « betagouv- » ; les autres blocs sont conservés tels quels, à leur place.

Une page qui a un brouillon non publié n'est pas modifiée, pour ne pas publier
par erreur le travail en cours d'un éditeur.
"""

import logging
from dataclasses import dataclass, field

from django.utils.text import slugify
from wagtail.models import Page, Site

from blog.models import Category
from fabrique import betagouv, images
from fabrique.betagouv import Product
from fabrique.models import ProduitPage, ProduitsIndexPage

logger = logging.getLogger(__name__)

OWNED_PREFIX = "betagouv-"


@dataclass
class Report:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    unpublished: list[str] = field(default_factory=list)
    skipped_drafts: list[str] = field(default_factory=list)


@dataclass
class Options:
    with_images: bool = True
    load_images: callable = betagouv.load_startup_images
    import_image: callable = images.import_image
    default_avatar: callable = images.default_avatar


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------


def _publish(page: Page) -> None:
    page.save_revision(log_action=True).publish()


def _unique_slug(parent: Page, base: str) -> str:
    slug, n = base or "produit", 2
    while parent.get_children().filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def _normalize(stream_block, raw: list[dict]) -> list[dict]:
    """Passe des blocs bruts par Wagtail pour obtenir exactement ce qui serait enregistré en base."""
    return list(stream_block.get_prep_value(stream_block.to_python(raw)))


def merge_owned_blocks(existing: list[dict], owned: list[dict]) -> list[dict]:
    """Remplace les blocs « betagouv- » sur place, retire ceux qui ne sont plus produits,
    ajoute les nouveaux à la fin et conserve tous les autres blocs tels quels."""
    owned_by_id = {b["id"]: b for b in owned}
    merged, seen = [], set()
    for block in existing:
        block_id = str(block.get("id") or "")
        if block_id.startswith(OWNED_PREFIX):
            if block_id in owned_by_id:
                merged.append(owned_by_id[block_id])
                seen.add(block_id)
            continue
        merged.append(block)
    merged.extend(b for b in owned if b["id"] not in seen)
    return merged


# Catégories d'actualités du site qui ne se déduisent pas du nom du produit.
NEWS_CATEGORIES = {
    "bat-id": "referentiel-national-du-batiment",
    "vues-immersives-libres": "panoramax",
    "ban": "base-adresse-nationale",
}


def guess_news_category(product: Product) -> Category | None:
    candidates = [NEWS_CATEGORIES.get(product.id), slugify(product.short_name), slugify(product.name), product.id]
    for slug in filter(None, candidates):
        category = Category.objects.filter(slug=slug).first()
        if category:
            return category
    return None


# ---------------------------------------------------------------------------
# Catalogue et fiches produits
# ---------------------------------------------------------------------------


def get_or_create_products_index(root: Page, slug: str, report: Report) -> ProduitsIndexPage:
    index = ProduitsIndexPage.objects.child_of(root).filter(slug=slug).first()
    if index:
        return index
    index = ProduitsIndexPage(
        title="Les produits de la Fabrique",
        slug=slug,
        show_in_menus=True,
        search_description=(
            "Les services numériques accompagnés par la Fabrique de la donnée territoriale, "
            "de l'investigation à la pérennisation."
        ),
        body=[
            {
                "type": "paragraph",
                "id": "introduction",
                "value": "<p>La Fabrique accompagne des équipes qui construisent des services publics numériques "
                "à partir de données territoriales harmonisées. Chaque produit avance par phases : "
                "investigation, construction, accélération, puis consolidation et pérennisation.</p>",
            }
        ],
    )
    root.add_child(instance=index)
    _publish(index)
    report.created.append(f"Page {index.title}")
    return index


def product_values(product: Product, page: ProduitPage | None, options: Options) -> dict:
    """Valeurs des champs synchronisés d'une fiche, images comprises."""
    previous_photos = {m.get("id"): m.get("photo") for m in (page.membres if page else [])}
    capture = page.capture if page else None
    photos: dict[str, str] | None = None  # None : photos inconnues, on garde les précédentes

    if options.with_images:
        loaded = options.load_images(product.id)
        if loaded is not None:
            shot_url, photos = loaded
            capture = options.import_image(shot_url, f"Capture d'écran — {product.name}") if shot_url else None

    membres = []
    for m in product.members:
        photo_id = previous_photos.get(m.id)
        if photos is not None:
            url = photos.get(betagouv.name_key(m.fullname))
            image = options.import_image(url, m.fullname) if url else None
            photo_id = image.id if image else None
        membres.append({"id": m.id, "nom": m.fullname, "role": m.role, "employeur": m.employer, "photo": photo_id})

    return {
        "title": product.name,
        "search_description": product.pitch,
        "pitch": product.pitch,
        "phase": product.phase,
        "phases": product.phases,
        "lien_site": product.link,
        "depot": product.repository,
        "contact": product.contact,
        "stats_url": product.stats_url,
        "budget_url": product.budget_url,
        "impact_url": product.impact_url,
        "porteurs": product.sponsors,
        "technos": product.technos,
        "description_betagouv": product.markdown,
        "membres": membres,
        "capture": capture,
    }


def sync_products(index: ProduitsIndexPage, products: list[Product], report: Report, options: Options) -> dict:
    """Crée ou met à jour une fiche par produit actif et dépublie celles des produits sortis.

    Renvoie {identifiant du produit : fiche}."""
    pages = {p.betagouv_id: p for p in ProduitPage.objects.child_of(index)}
    result: dict[str, ProduitPage] = {}

    for product in products:
        page = pages.get(product.id)
        if page is not None and page.has_unpublished_changes:
            logger.warning("%s : brouillon non publié, fiche laissée telle quelle.", product.name)
            report.skipped_drafts.append(product.name)
            result[product.id] = page
            continue

        values = product_values(product, page, options)
        if page is None or page.categorie_actualites_id is None:
            # Seulement tant qu'elle est vide : un éditeur peut ensuite la changer librement.
            category = guess_news_category(product)
            if category:
                values["categorie_actualites"] = category
        if page is None:
            page = ProduitPage(betagouv_id=product.id, slug=_unique_slug(index, slugify(product.id.replace(".", "-"))))
            for name, value in values.items():
                setattr(page, name, value)
            index.add_child(instance=page)
            _publish(page)
            report.created.append(product.name)
        else:
            changed = [name for name, value in values.items() if getattr(page, name) != value]
            if changed or not page.live:
                for name in changed:
                    setattr(page, name, values[name])
                _publish(page)
                report.updated.append(product.name)
            else:
                report.unchanged.append(product.name)
        result[product.id] = page

    active = {p.id for p in products}
    for product_id, page in pages.items():
        if product_id not in active and page.live:
            # Produit arrêté ou rattaché à un autre incubateur : la fiche reste dans Wagtail, hors ligne.
            page.unpublish(log_action=True)
            report.unpublished.append(page.title)
    return result


# ---------------------------------------------------------------------------
# Page Équipe
# ---------------------------------------------------------------------------


def team_owned_blocks(
    products: list[Product], pages: dict[str, ProduitPage], default_photo: int | None = None
) -> list[dict]:
    """Section « Les équipes produits » : une carte par personne (photo, rôle, structure), produits en étiquettes."""
    people: dict[str, dict] = {}
    for product in products:
        page = pages.get(product.id)
        photos = {m["id"]: m.get("photo") for m in (page.membres if page else [])}
        for m in product.members:
            person = people.setdefault(m.id, {"member": m, "products": [], "photo": None})
            person["products"].append(product)
            person["photo"] = person["photo"] or photos.get(m.id)

    cards = []
    for member_id, person in sorted(people.items(), key=lambda kv: kv[1]["member"].fullname.split()[-1].lower()):
        m = person["member"]
        tags = [
            {
                "type": "tag",
                "id": f"{OWNED_PREFIX}tag-{member_id}-{p.id}",
                "value": {
                    "label": p.short_name,
                    "is_small": True,
                    "color": "",
                    "icon_class": "",
                    "link": {"page": pages[p.id].id if p.id in pages else None, "document": None, "external_url": ""},
                },
            }
            for p in person["products"]
        ]
        cards.append(
            {
                "type": "contact_card",
                "id": f"{OWNED_PREFIX}personne-{member_id}",
                "value": {
                    "contact": None,
                    "link": {"page": None, "document": None, "external_url": ""},
                    "heading_tag": "h3",
                    "name": m.fullname,
                    "role": m.role,
                    "organization": m.employer,
                    "contact_info": "",
                    "image": person["photo"] or default_photo,
                    "tags": tags,
                },
            }
        )

    if not cards:
        return []
    return [
        {
            "type": "paragraph",
            "id": f"{OWNED_PREFIX}equipes-titre",
            "value": "<h2>Les équipes produits</h2>"
            "<p>Les personnes engagées aujourd’hui sur les produits accompagnés par la Fabrique.</p>",
        },
        {
            "type": "item_grid",
            "id": f"{OWNED_PREFIX}equipes",
            "value": {"column_width": "3", "horizontal_align": "left", "vertical_align": "", "items": cards},
        },
    ]


def sync_team_page(
    root: Page,
    slug: str,
    products: list[Product],
    pages: dict[str, ProduitPage],
    report: Report,
    default_photo: int | None = None,
):
    page = Page.objects.child_of(root).filter(slug=slug).specific().first()
    if page is None or not hasattr(page, "body"):
        logger.warning("Page Équipe « %s » introuvable : section des équipes produits non mise à jour.", slug)
        return
    label = f"Page {page.title}"
    if page.has_unpublished_changes:
        logger.warning("%s : brouillon non publié, page laissée telle quelle.", label)
        report.skipped_drafts.append(label)
        return
    stream_block = page.body.stream_block
    existing = _normalize(stream_block, list(page.body.raw_data))
    new_body = _normalize(
        stream_block, merge_owned_blocks(existing, team_owned_blocks(products, pages, default_photo))
    )
    if new_body == existing:
        report.unchanged.append(label)
        return
    page.body = new_body
    _publish(page)
    report.updated.append(label)


def run(products: list[Product], products_slug: str, team_slug: str, options: Options | None = None) -> Report:
    options = options or Options()
    report = Report()
    root = Site.objects.get(is_default_site=True).root_page.specific
    index = get_or_create_products_index(root, products_slug, report)
    pages = sync_products(index, products, report, options)
    avatar = options.default_avatar() if options.with_images else None
    sync_team_page(root, team_slug, products, pages, report, avatar.id if avatar else None)
    return report
