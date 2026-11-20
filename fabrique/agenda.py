"""Écriture de l'agenda Grist dans les pages Événement de Sites Faciles.

- Page « Agenda » (EventsIndexPage de l'app events), créée si elle n'existe pas :
  elle fournit la liste des événements à venir, les archives, le filtre par
  étiquette et l'export iCal.
- Une page Événement (EventEntryPage) par événement publié dans Grist. La
  synchronisation possède le titre, les dates, le lieu, le lien d'inscription,
  les étiquettes (type, équipes, séries) et les blocs du corps dont l'identifiant
  commence par « grist- ». Les autres blocs et les réglages restent aux éditeurs.
- Le type et les équipes sont aussi gardés à part (EtiquettesEvenement) pour être
  affichés sur la carte de l'événement dans la liste de l'agenda.
- L'image de l'événement (colonne Image, pièce jointe) devient l'image d'en-tête
  de la page : vignette dans la liste de l'agenda et dans la fiche de
  l'événement, bandeau en haut de la page. Les images importées sont rangées dans
  la collection « Agenda » de Wagtail. Une image d'en-tête choisie à la main
  dans Wagtail (hors de cette collection) n'est remplacée que si l'événement a
  une image dans Grist.
- Une page dont l'événement a été dépublié ou supprimé dans Grist est dépubliée,
  mais reste dans Wagtail. Les événements passés restent en ligne (archives).

Une page qui a un brouillon non publié n'est pas modifiée, pour ne pas publier
par erreur le travail en cours d'un éditeur.
"""

import html
import logging
import re
from dataclasses import dataclass
from io import BytesIO

from django.core.files.images import ImageFile
from django.utils.text import slugify
from wagtail.images import get_image_model
from wagtail.models import Collection, Page, Site

from events.models import EventEntryPage, EventsIndexPage
from fabrique import grist
from fabrique.grist import Evenement
from fabrique.models import EtiquettesEvenement
from fabrique.sync import Report, _normalize, _publish, _unique_slug

logger = logging.getLogger(__name__)

OWNED_PREFIX = "grist-"
PREFIXE_ANNULE = "Annulé : "
COLLECTION_IMAGES = "Agenda"
EXTENSIONS_IMAGES = {"jpg", "jpeg", "png", "webp", "gif"}
TAILLE_MAX_IMAGE = 10 * 1024 * 1024


@dataclass
class Source:
    """Document Grist lu : sert à fabriquer et reconnaître le lien de chaque page vers sa ligne."""

    base_url: str = grist.DEFAULT_BASE_URL
    org: str = grist.DEFAULT_ORG
    doc_id: str = grist.DEFAULT_DOC_ID

    def url(self, row_id: int) -> str:
        return grist.source_url(self.base_url, self.org, self.doc_id, row_id)

    def row_id(self, page: Page) -> int | None:
        return grist.row_id_from_source_url(page.source_url, self.doc_id)


# ---------------------------------------------------------------------------
# Corps de la page
# ---------------------------------------------------------------------------


def merge_owned_group(existing: list[dict], owned: list[dict], prefix: str = OWNED_PREFIX) -> list[dict]:
    """Remplace les blocs possédés par la synchronisation par le nouveau groupe `owned`, d'un seul tenant.

    Le groupe prend la place du premier bloc possédé existant (ou le début du corps s'il n'y en avait pas) :
    un bloc ajouté plus tard, comme l'alerte d'annulation, garde ainsi sa place dans le groupe.
    Les autres blocs sont conservés tels quels, dans leur ordre."""
    merged, inserted = [], False
    for block in existing:
        if str(block.get("id") or "").startswith(prefix):
            if not inserted:
                merged.extend(owned)
                inserted = True
            continue
        merged.append(block)
    if not inserted:
        merged = owned + merged
    return merged


def _bouton(id: str, texte: str, url: str, style: str, icone: str) -> dict:
    return {
        "type": "button",
        "id": f"{OWNED_PREFIX}bouton-{id}",
        "value": {
            "page": None,
            "document": None,
            "external_url": url,
            "text": texte,
            "button_type": style,
            "icon_class": icone,
            "icon_side": "fr-btn--icon-left",
        },
    }


def owned_blocks(ev: Evenement) -> list[dict]:
    blocks = []
    if ev.annule:
        blocks.append(
            {
                "type": "alert",
                "id": f"{OWNED_PREFIX}annule",
                "value": {
                    "title": "Événement annulé",
                    "description": "Cet événement n'aura pas lieu.",
                    "level": "warning",
                    "heading_tag": "h2",
                },
            }
        )

    infos = []
    if ev.public:
        infos.append(f"<p><b>Public :</b> {html.escape(ev.public)}</p>")
    if ev.places_restantes is not None and not ev.annule:
        places = "Complet" if ev.places_restantes == 0 else f"{ev.places_restantes}"
        infos.append(f"<p><b>Places restantes :</b> {places}</p>")
    if infos:
        blocks.append({"type": "paragraph", "id": f"{OWNED_PREFIX}infos", "value": "".join(infos)})

    if ev.description:
        blocks.append({"type": "markdown", "id": f"{OWNED_PREFIX}description", "value": ev.description})

    boutons = []
    if ev.lien_inscription and not ev.annule:
        boutons.append(_bouton("inscription", "S'inscrire", ev.lien_inscription, "fr-btn", "fr-icon-edit-line"))
    if ev.lien_visio and not ev.annule:
        boutons.append(
            _bouton("visio", "Rejoindre la visio", ev.lien_visio, "fr-btn fr-btn--secondary", "fr-icon-live-line")
        )
    if ev.lien_evenement:
        boutons.append(
            _bouton(
                "page",
                "Page de l'événement",
                ev.lien_evenement,
                "fr-btn fr-btn--secondary",
                "fr-icon-external-link-line",
            )
        )
    if ev.lien_outlook:
        boutons.append(
            _bouton(
                "outlook", "Ajouter à Outlook", ev.lien_outlook, "fr-btn fr-btn--tertiary", "fr-icon-calendar-line"
            )
        )
    if boutons:
        blocks.append(
            {"type": "buttons_list", "id": f"{OWNED_PREFIX}liens", "value": {"buttons": boutons, "position": ""}}
        )
    return blocks


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


class Images:
    """Importe dans Wagtail les images des événements, une seule fois chacune.

    Le nom du fichier importé contient l'identifiant et la taille de la pièce jointe Grist : on retrouve ainsi
    l'image déjà importée sans retélécharger le fichier à chaque synchronisation."""

    def __init__(self, pieces_jointes: "grist.PiecesJointes | None", doc_id: str):
        self.pieces_jointes, self.doc_id = pieces_jointes, doc_id
        self._collection: Collection | None = None

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            root = Collection.get_first_root_node()
            self._collection = root.get_children().filter(name=COLLECTION_IMAGES).first() or root.add_child(
                name=COLLECTION_IMAGES
            )
        return self._collection

    def owns(self, image) -> bool:
        return image is not None and image.collection_id == self.collection.id

    def get(self, ev: Evenement):
        """Image Wagtail de l'événement, ou None (pas d'image, fichier refusé ou Grist injoignable)."""
        if not ev.image or self.pieces_jointes is None:
            return None
        try:
            infos = self.pieces_jointes.infos(ev.image)
        except RuntimeError as e:
            logger.warning("%s : liste des pièces jointes illisible (%s).", ev.titre, e)
            return None
        if not infos:
            return None
        nom = str(infos.get("fileName") or "")
        extension = nom.rsplit(".", 1)[-1].lower() if "." in nom else ""
        taille = infos.get("fileSize") or 0
        if extension not in EXTENSIONS_IMAGES:
            logger.warning("%s : « %s » n'est pas une image JPG, PNG, WebP ou GIF, ignorée.", ev.titre, nom)
            return None
        if taille > TAILLE_MAX_IMAGE:
            logger.warning("%s : image « %s » trop lourde (%s octets), ignorée.", ev.titre, nom, taille)
            return None

        cle = f"grist-{self.doc_id}-{ev.image}-{taille}"
        Image = get_image_model()
        image = Image.objects.filter(collection=self.collection, file__contains=cle).first()
        if image is not None:
            return image
        try:
            contenu = self.pieces_jointes.download(ev.image)
        except RuntimeError as e:
            logger.warning("%s : image « %s » non téléchargée (%s).", ev.titre, nom, e)
            return None
        image = Image(title=ev.titre[:255], collection=self.collection)
        image.file = ImageFile(BytesIO(contenu), name=f"{cle}.{extension}")
        image._set_image_file_metadata()
        image.save()
        return image

    def resolve(self, ev: Evenement, actuelle):
        """Image d'en-tête à donner à la page, compte tenu de celle qu'elle a déjà."""
        image = self.get(ev)
        if image is not None:
            return image
        if not ev.image and self.owns(actuelle):
            # Image retirée dans Grist : on retire celle qu'on avait importée.
            return None
        # Pas d'image dans Grist et image choisie à la main, ou image Grist momentanément illisible : on garde.
        return actuelle


# ---------------------------------------------------------------------------
# Champs de la page
# ---------------------------------------------------------------------------


def _resume(ev: Evenement, longueur: int = 160) -> str:
    """Description courte pour les moteurs de recherche, à partir du texte markdown."""
    texte = re.sub(r"[#*_`>\[\]]|\(https?://[^)]*\)", "", ev.description)
    texte = " ".join(texte.split())
    if len(texte) > longueur:
        texte = texte[: longueur - 1].rsplit(" ", 1)[0] + "…"
    return texte


def event_values(ev: Evenement, source: Source) -> dict:
    lieu = ev.lieu or ("En ligne" if ev.lien_visio else "")
    return {
        "title": f"{PREFIXE_ANNULE}{ev.titre}" if ev.annule else ev.titre,
        "event_date_start": ev.debut,
        "event_date_end": ev.fin,
        "location": lieu[:200] or None,
        "registration_url": (ev.lien_inscription or None) if not ev.annule else None,
        "search_description": _resume(ev),
        "source_url": source.url(ev.id),
    }


def _tags(page: EventEntryPage) -> list[str]:
    return sorted(t.name for t in page.tags.all())


def _enregistrer_etiquettes(page: EventEntryPage, ev: Evenement) -> None:
    """Type et équipes affichés sur la carte de l'événement. Hors révisions : ne republie pas la page."""
    valeurs = {"type": ev.type[:100], "equipes": ev.equipes}
    actuelles = EtiquettesEvenement.objects.filter(page=page).values("type", "equipes").first()
    if actuelles != valeurs:
        EtiquettesEvenement.objects.update_or_create(page=page, defaults=valeurs)


# ---------------------------------------------------------------------------
# Synchronisation
# ---------------------------------------------------------------------------


def get_or_create_agenda(root: Page, slug: str, report: Report) -> EventsIndexPage:
    page = Page.objects.child_of(root).filter(slug=slug).specific().first()
    if isinstance(page, EventsIndexPage):
        return page
    if page is not None:
        raise RuntimeError(
            f"La page « /{slug}/ » existe mais n'est pas un calendrier d'événements ({page.specific_class.__name__}). "
            "Renommez-la ou indiquez une autre adresse avec FABRIQUE_AGENDA_SLUG."
        )
    index = EventsIndexPage(
        title="Agenda",
        slug=slug,
        show_in_menus=True,
        filter_by_category=False,
        filter_by_tag=True,
        search_description="Les événements de la Fabrique de la donnée territoriale et de ses équipes produits.",
        body=[
            {
                "type": "paragraph",
                "id": "introduction",
                "value": "<p>Webinaires, ateliers, démonstrations et rencontres de la Fabrique de la donnée "
                "territoriale et de ses équipes produits.</p>",
            }
        ],
    )
    root.add_child(instance=index)
    _publish(index)
    report.created.append(f"Page {index.title}")
    return index


def sync_events(
    index: EventsIndexPage, evenements: list[Evenement], source: Source, report: Report, images: Images
) -> None:
    pages: dict[int, EventEntryPage] = {}
    for page in EventEntryPage.objects.child_of(index):
        row_id = source.row_id(page)
        if row_id is not None:
            pages[row_id] = page

    for ev in evenements:
        page = pages.get(ev.id)
        label = ev.titre
        # Une page hors ligne a toujours des « modifications non publiées » (la dépublication en est une) :
        # seul le brouillon d'une page en ligne est le signe d'un travail en cours.
        if page is not None and page.live and page.has_unpublished_changes:
            logger.warning("%s : brouillon non publié, page laissée telle quelle.", label)
            report.skipped_drafts.append(label)
            continue

        values = event_values(ev, source)
        values["header_image"] = images.resolve(ev, page.header_image if page is not None else None)
        tags = sorted(ev.etiquettes)
        if page is None:
            page = EventEntryPage(slug=_unique_slug(index, slugify(ev.titre)[:80] or "evenement"), **values)
            page.body = owned_blocks(ev)
            page.tags.set(tags)
            index.add_child(instance=page)
            _publish(page)
            _enregistrer_etiquettes(page, ev)
            report.created.append(label)
            continue

        _enregistrer_etiquettes(page, ev)

        stream_block = page.body.stream_block
        existing = _normalize(stream_block, list(page.body.raw_data))
        new_body = _normalize(stream_block, merge_owned_group(existing, owned_blocks(ev)))
        changed = [name for name, value in values.items() if getattr(page, name) != value]
        body_changed = new_body != existing
        tags_changed = _tags(page) != tags
        if changed or body_changed or tags_changed or not page.live:
            for name in changed:
                setattr(page, name, values[name])
            if body_changed:
                page.body = new_body
            if tags_changed:
                page.tags.set(tags)
            _publish(page)
            report.updated.append(label)
        else:
            report.unchanged.append(label)

    publies = {ev.id for ev in evenements}
    for row_id, page in pages.items():
        if row_id not in publies and page.live:
            # Décoché « Publié » ou supprimé dans Grist : la page reste dans Wagtail, hors ligne.
            page.unpublish(log_action=True)
            report.unpublished.append(page.title)


def synced_live_pages(slug: str, source: Source) -> int:
    """Nombre de pages en ligne issues de Grist (pour le garde-fou contre une table vide)."""
    root = Site.objects.get(is_default_site=True).root_page
    index = EventsIndexPage.objects.child_of(root).filter(slug=slug).first()
    if index is None:
        return 0
    return sum(1 for p in EventEntryPage.objects.child_of(index).live() if source.row_id(p) is not None)


def run(
    evenements: list[Evenement],
    slug: str,
    source: Source | None = None,
    pieces_jointes: "grist.PiecesJointes | None" = None,
) -> Report:
    source = source or Source()
    report = Report()
    root = Site.objects.get(is_default_site=True).root_page.specific
    index = get_or_create_agenda(root, slug, report)
    sync_events(index, evenements, source, report, Images(pieces_jointes, source.doc_id))
    return report
