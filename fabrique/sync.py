"""Écriture des produits et des équipes beta.gouv.fr dans les pages Wagtail.

Principe : la synchronisation ne possède que certains blocs de chaque page,
reconnaissables à leur identifiant qui commence par « betagouv- ». Elle les
crée, les met à jour ou les retire, et ne touche jamais aux autres blocs : tout
ce qui est ajouté à la main dans Wagtail est conservé, à sa place.

Pages concernées :
- la page catalogue « Produits » (créée si elle n'existe pas) ;
- une page de contenu par produit actif, sous la page Produits, retrouvée grâce
  à son champ « URL source » (adresse de la fiche beta.gouv.fr) ;
- la page Équipe, où une section « Les équipes produits » est ajoutée.

Une page qui a un brouillon non publié n'est pas modifiée, pour ne pas publier
par erreur le travail en cours d'un éditeur : elle sera mise à jour à la
synchronisation suivante, une fois le brouillon publié.
"""

import json
import logging
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from django.utils.text import slugify
from wagtail.models import Page, Site

from content_manager.models import CatalogIndexPage, ContentPage
from fabrique.betagouv import STARTUP_PAGE_URL, Product

logger = logging.getLogger(__name__)

OWNED_PREFIX = "betagouv-"
SOURCE_URL_PREFIX = STARTUP_PAGE_URL.split("{")[0]
PRESENTATIONS = json.loads((Path(__file__).parent / "data" / "presentations.json").read_text(encoding="utf-8"))


@dataclass
class Report:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    unpublished: list[str] = field(default_factory=list)
    skipped_drafts: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Construction des blocs
# ---------------------------------------------------------------------------


def _empty_link(page_id: int | None = None, url: str = "") -> dict:
    return {"page": page_id, "document": None, "external_url": url}


def _paragraph(block_id: str, html: str) -> dict:
    return {"type": "paragraph", "id": block_id, "value": html}


def _contact_card(block_id: str, name: str, role: str, organization: str, tags: list[dict] | None = None) -> dict:
    return {
        "type": "contact_card",
        "id": block_id,
        "value": {
            "contact": None,
            "link": _empty_link(),
            "heading_tag": "h3",
            "name": name,
            "role": role,
            "organization": organization,
            "contact_info": "",
            "image": None,
            "tags": tags or [],
        },
    }


def _grid(block_id: str, items: list[dict], column_width: str = "4") -> dict:
    return {
        "type": "item_grid",
        "id": block_id,
        "value": {"column_width": column_width, "horizontal_align": "left", "vertical_align": "", "items": items},
    }


def product_owned_blocks(product: Product) -> list[dict]:
    """Blocs gérés par la synchronisation sur la page d'un produit, dans leur ordre par défaut."""
    blocks = [
        {
            "type": "badges_list",
            "id": f"{OWNED_PREFIX}phase",
            "value": [
                {
                    "type": "badge",
                    "id": f"{OWNED_PREFIX}phase-badge",
                    "value": {"text": product.phase_label, "color": product.phase_color, "hide_icon": True},
                }
            ],
        }
    ]
    if product.pitch:
        blocks.append(_paragraph(f"{OWNED_PREFIX}mission", f"<p><b>Mission :</b> {escape(product.pitch)}</p>"))

    links = []
    if product.link:
        links.append(f'<li><a href="{escape(product.link)}">Site du produit</a></li>')
    if product.repository:
        links.append(f'<li><a href="{escape(product.repository)}">Code source</a></li>')
    links.append(f'<li><a href="{escape(product.source_url)}">Fiche du produit sur beta.gouv.fr</a></li>')
    if product.contact:
        links.append(f'<li>Contact : <a href="mailto:{escape(product.contact)}">{escape(product.contact)}</a></li>')
    infos = f"<h2>En savoir plus</h2><ul>{''.join(links)}</ul>"
    if product.sponsors:
        infos += f"<p><b>Porteurs :</b> {escape(', '.join(product.sponsors))}</p>"
    blocks.append(_paragraph(f"{OWNED_PREFIX}liens", infos))

    if product.members:
        blocks.append(_paragraph(f"{OWNED_PREFIX}equipe-titre", "<h2>L’équipe</h2>"))
        blocks.append(
            _grid(
                f"{OWNED_PREFIX}equipe",
                [
                    _contact_card(f"{OWNED_PREFIX}membre-{m.id}", m.fullname, m.role, m.employer)
                    for m in product.members
                ],
            )
        )
    return blocks


def product_initial_blocks(product: Product) -> list[dict]:
    """Corps d'une nouvelle page produit : blocs synchronisés + présentation modifiable à la main."""
    owned = product_owned_blocks(product)
    text = PRESENTATIONS.get(product.id)
    if text:
        presentation = _paragraph("presentation", f"<p>{escape(text)}</p>")
    elif product.markdown:
        presentation = {"type": "markdown", "id": "presentation", "value": product.markdown}
    else:
        presentation = None
    if presentation:
        # Après le badge et la mission, avant les liens et l'équipe.
        position = next((i for i, b in enumerate(owned) if b["id"] == f"{OWNED_PREFIX}liens"), len(owned))
        owned.insert(position, presentation)
    return owned


def team_owned_blocks(products: list[Product], product_pages: dict[str, int]) -> list[dict]:
    """Section « Les équipes produits » de la page Équipe : une carte par personne, produits en étiquettes."""
    people: dict[str, dict] = {}
    for product in products:
        for m in product.members:
            person = people.setdefault(m.id, {"member": m, "products": []})
            person["products"].append(product)

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
                    "link": _empty_link(product_pages.get(p.id)),
                },
            }
            for p in person["products"]
        ]
        cards.append(_contact_card(f"{OWNED_PREFIX}personne-{member_id}", m.fullname, m.role, m.employer, tags))

    if not cards:
        return []
    return [
        _paragraph(
            f"{OWNED_PREFIX}equipes-titre",
            "<h2>Les équipes produits</h2>"
            "<p>Les personnes engagées aujourd’hui sur les produits accompagnés par la Fabrique.</p>",
        ),
        _grid(f"{OWNED_PREFIX}equipes", cards),
    ]


# ---------------------------------------------------------------------------
# Fusion avec le contenu existant
# ---------------------------------------------------------------------------


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


def _publish(page: Page) -> None:
    page.save_revision(log_action=True).publish()


def _update_page(page: Page, owned: list[dict], report: Report, label: str, **fields) -> None:
    page = page.specific
    if page.has_unpublished_changes:
        logger.warning("%s : brouillon non publié, page laissée telle quelle.", label)
        report.skipped_drafts.append(label)
        return

    stream_block = page.body.stream_block
    existing = list(page.body.raw_data)
    new_body = _normalize(stream_block, merge_owned_blocks(existing, _normalize(stream_block, owned)))

    changed = new_body != _normalize(stream_block, existing)
    for name, value in fields.items():
        if name == "tags":
            if sorted(t.name for t in page.tags.all()) != sorted(value):
                page.tags.set(value, clear=True)
                changed = True
        elif getattr(page, name) != value:
            setattr(page, name, value)
            changed = True

    if not changed and page.live:
        report.unchanged.append(label)
        return
    page.body = new_body
    _publish(page)
    report.updated.append(label)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def _unique_slug(parent: Page, base: str) -> str:
    slug, n = base, 2
    while parent.get_children().filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def get_or_create_products_index(root: Page, slug: str, report: Report) -> CatalogIndexPage:
    index = CatalogIndexPage.objects.child_of(root).filter(slug=slug).first()
    if index:
        return index
    index = CatalogIndexPage(
        title="Les produits de la Fabrique",
        slug=slug,
        show_in_menus=True,
        body=[
            _paragraph(
                "introduction",
                "<p>La Fabrique accompagne des équipes qui construisent des services publics numériques "
                "à partir de données territoriales harmonisées. Chaque produit avance par phases : "
                "investigation, construction, accélération, puis consolidation et pérennisation.</p>",
            )
        ],
    )
    root.add_child(instance=index)
    _publish(index)
    report.created.append(f"Page {index.title}")
    return index


def sync_products(index: CatalogIndexPage, products: list[Product], inactive_ids: set[str], report: Report) -> dict:
    """Crée ou met à jour une page par produit actif et dépublie celles des produits sortis.

    Renvoie {identifiant du produit : identifiant de sa page}."""
    pages_by_source = {
        p.source_url: p for p in ContentPage.objects.child_of(index).filter(source_url__startswith=SOURCE_URL_PREFIX)
    }
    product_pages: dict[str, int] = {}

    for product in products:
        fields = {
            "title": product.name,
            "search_description": product.pitch,
            "tags": [product.phase_label],
        }
        page = pages_by_source.get(product.source_url)
        if page is None:
            page = ContentPage(
                title=product.name,
                slug=_unique_slug(index, slugify(product.id.replace(".", "-"))),
                search_description=product.pitch,
                source_url=product.source_url,
                body=product_initial_blocks(product),
            )
            index.add_child(instance=page)
            page.tags.set([product.phase_label])
            _publish(page)
            report.created.append(product.name)
        else:
            _update_page(page, product_owned_blocks(product), report, product.name, **fields)
        product_pages[product.id] = page.id

    active_sources = {p.source_url for p in products}
    for source_url, page in pages_by_source.items():
        if source_url not in active_sources and page.live:
            # Produit abandonné, ou rattaché à un autre incubateur : la page reste dans Wagtail, hors ligne.
            page.unpublish(log_action=True)
            report.unpublished.append(page.title)
    return product_pages


def sync_team_page(root: Page, slug: str, products: list[Product], product_pages: dict[str, int], report: Report):
    page = Page.objects.child_of(root).filter(slug=slug).specific().first()
    if page is None or not hasattr(page, "body"):
        logger.warning("Page Équipe « %s » introuvable : section des équipes produits non mise à jour.", slug)
        return
    _update_page(page, team_owned_blocks(products, product_pages), report, f"Page {page.title}")


def run(products: list[Product], inactive_ids: set[str], products_slug: str, team_slug: str) -> Report:
    report = Report()
    root = Site.objects.get(is_default_site=True).root_page.specific
    index = get_or_create_products_index(root, products_slug, report)
    product_pages = sync_products(index, products, inactive_ids, report)
    sync_team_page(root, team_slug, products, product_pages, report)
    return report
