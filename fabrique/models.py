from datetime import date

from django.db import models
from django.utils.formats import date_format
from django.utils.text import slugify
from wagtail.admin.panels import FieldPanel, HelpPanel, MultiFieldPanel
from wagtail.images import get_image_model, get_image_model_string
from wagtail.models import Page

from content_manager.abstract import SitesFacilesBasePage
from fabrique.betagouv import PHASES

# Libellés des phases pour la frise « En quelques dates » (y compris les phases de sortie).
PHASE_TIMELINE_LABELS = {
    **{key: value[0] for key, value in PHASES.items()},
    "abandon": "Arrêté",
    "abandon-investigation": "Arrêté après investigation",
}

SYNC_HELP = (
    "Les informations ci-dessous sont mises à jour chaque nuit depuis la fiche du produit sur beta.gouv.fr. "
    "Pour les corriger, modifiez la fiche dans l'espace membre beta.gouv.fr. "
    "Le corps de la page, l'image d'en-tête et les réglages restent modifiables ici et ne sont jamais écrasés."
)


class ImageImportee(models.Model):
    """Image de la médiathèque importée depuis une adresse (photo de membre, capture d'écran de produit).

    Permet de ne télécharger chaque image qu'une fois et de la remplacer si elle change à la source.
    """

    url = models.URLField("Adresse d'origine", max_length=1000, unique=True)
    empreinte = models.CharField("Empreinte SHA-256", max_length=64)
    image = models.ForeignKey(get_image_model_string(), on_delete=models.CASCADE, related_name="+")

    class Meta:
        verbose_name = "Image importée"
        verbose_name_plural = "Images importées"

    def __str__(self):
        return self.url


class ProduitsIndexPage(SitesFacilesBasePage):
    """Catalogue des produits : une carte par fiche produit, avec un filtre par phase."""

    subpage_types = ["fabrique.ProduitPage"]
    template = "fabrique/produits_index_page.html"

    class Meta:
        verbose_name = "Catalogue des produits"

    def produits(self):
        pages = ProduitPage.objects.child_of(self).live().public().specific().select_related("capture")
        return sorted(pages, key=lambda p: (p.phase_order, p.title.lower()))

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        produits = self.produits()
        phases: dict[str, dict] = {}
        for produit in produits:
            phase = phases.setdefault(produit.phase_slug, {"label": produit.phase_label, "slug": produit.phase_slug})
            phase["count"] = phase.get("count", 0) + 1
        current = request.GET.get("phase", "")
        if current in phases:
            produits = [p for p in produits if p.phase_slug == current]
        else:
            current = ""
        context.update({"produits": produits, "phases": list(phases.values()), "phase_courante": current})
        return context


class ProduitPage(SitesFacilesBasePage):
    """Fiche d'un produit accompagné par la Fabrique, alimentée par la synchronisation beta.gouv.fr."""

    betagouv_id = models.CharField("Identifiant beta.gouv.fr", max_length=200, unique=True)
    pitch = models.TextField("Mission", blank=True)
    phase = models.CharField("Phase actuelle", max_length=50, blank=True)
    phases = models.JSONField("Historique des phases", default=list, blank=True)
    lien_site = models.URLField("Site du produit", max_length=500, blank=True)
    depot = models.URLField("Code source", max_length=500, blank=True)
    contact = models.CharField("Contact", max_length=255, blank=True)
    stats_url = models.URLField("Statistiques", max_length=500, blank=True)
    budget_url = models.URLField("Budget", max_length=500, blank=True)
    impact_url = models.URLField("Impact", max_length=500, blank=True)
    porteurs = models.JSONField("Porteurs", default=list, blank=True)
    technos = models.JSONField("Technologies", default=list, blank=True)
    description_betagouv = models.TextField(
        "Présentation beta.gouv.fr (markdown)",
        blank=True,
        help_text="Affichée tant que le corps de la page est vide.",
    )
    membres = models.JSONField("Équipe", default=list, blank=True)
    capture = models.ForeignKey(
        get_image_model_string(),
        verbose_name="Capture d'écran",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    parent_page_types = ["fabrique.ProduitsIndexPage"]
    subpage_types = []
    template = "fabrique/produit_page.html"

    content_panels = SitesFacilesBasePage.content_panels + [
        MultiFieldPanel(
            [
                HelpPanel(content=f"<p>{SYNC_HELP}</p>"),
                FieldPanel("betagouv_id", read_only=True),
                FieldPanel("phase", read_only=True),
                FieldPanel("pitch", read_only=True),
                FieldPanel("lien_site", read_only=True),
                FieldPanel("contact", read_only=True),
                FieldPanel("capture", read_only=True),
                FieldPanel("description_betagouv", read_only=True),
            ],
            heading="Données beta.gouv.fr (lecture seule)",
            classname="collapsed",
        ),
    ]

    class Meta:
        verbose_name = "Fiche produit"
        verbose_name_plural = "Fiches produits"

    # -- Affichage ---------------------------------------------------------

    @property
    def phase_label(self) -> str:
        return PHASES.get(self.phase, (PHASE_TIMELINE_LABELS.get(self.phase, self.phase), "", 99))[0]

    @property
    def phase_slug(self) -> str:
        return slugify(self.phase_label)

    @property
    def phase_color(self) -> str:
        return PHASES.get(self.phase, ("", "grey", 99))[1]

    @property
    def phase_order(self) -> int:
        return PHASES.get(self.phase, ("", "", 99))[2]

    @property
    def lien_site_court(self) -> str:
        """« https://www.panoramax.fr/ » → « panoramax.fr »."""
        lien = self.lien_site.split("://", 1)[-1].rstrip("/")
        return lien.removeprefix("www.")

    def frise_phases(self) -> list[dict]:
        items = []
        dated = sorted((p for p in self.phases if p.get("name")), key=lambda p: str(p.get("start") or ""))
        for i, phase in enumerate(dated):
            try:
                start = date.fromisoformat(str(phase.get("start"))[:10])
                start_label = date_format(start, "j F Y")
            except ValueError:
                start_label = ""
            items.append(
                {
                    "label": PHASE_TIMELINE_LABELS.get(phase["name"], phase["name"]),
                    "date": start_label,
                    "courante": i == len(dated) - 1,
                }
            )
        return items

    def equipe(self) -> list[dict]:
        """Membres avec leur photo (objet image Wagtail) résolue en une seule requête."""
        ids = [m.get("photo") for m in self.membres if m.get("photo")]
        images = {img.id: img for img in get_image_model().objects.filter(id__in=ids)}
        return [{**m, "image": images.get(m.get("photo"))} for m in self.membres]

    def ressources(self) -> list[dict]:
        liens = [
            ("Code source", self.depot, "fr-icon-code-s-slash-line"),
            ("Budget", self.budget_url, "fr-icon-money-euro-circle-line"),
            ("Statistiques d'usage", self.stats_url, "fr-icon-line-chart-line"),
            ("Mesure de l'impact", self.impact_url, "fr-icon-line-chart-line"),
        ]
        return [{"label": label, "url": url, "icon": icon} for label, url, icon in liens if url]

    def a_un_corps(self) -> bool:
        return bool(self.body and len(self.body))

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["catalogue"] = Page.objects.get(id=self.get_parent().id).specific
        return context
