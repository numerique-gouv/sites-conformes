import zoneinfo
from datetime import datetime

from django.core.management.base import BaseCommand
from wagtail.models import Page

from blog.models import Organization
from content_manager.utils import get_default_site
from numerique_gouv.models import (
    HubPages,
    MajorArea,
    NumeriqueBlogEntryPage,
    NumeriqueBlogIndexPage,
    NumeriquePage,
    OffersEntryPage,
    OffersIndexPage,
    Offertype,
    PageTag,
    ProductsEntryPage,
    ProductsIndexPage,
    SitemapPage,
    TargetAudience,
)

PARIS_TZ = zoneinfo.ZoneInfo("Europe/Paris")


class Command(BaseCommand):
    help = """
    Creates the numerique_gouv pages used by the end-to-end tests (offers, products, news, hub, sitemap).
    The content is fixed (no random data, fixed dates) so that visual regression screenshots stay stable.
    The command is idempotent: existing pages and snippets are reused.
    """

    def handle(self, *args, **kwargs):
        self.home = get_default_site().root_page

        self.create_taxonomy()
        self.create_blog()
        self.create_offers()
        self.create_products()
        self.create_hub()
        self.create_sitemap()

    def create_taxonomy(self):
        def get_or_create(model, slug, name):
            obj, _created = model.objects.get_or_create(slug=slug, defaults={"name": name})
            return obj

        self.tag_ia = get_or_create(PageTag, "ia", "Intelligence artificielle")
        self.tag_data = get_or_create(PageTag, "donnees", "Données")
        self.area_cloud = get_or_create(MajorArea, "cloud", "Cloud")
        self.audience_agents = get_or_create(TargetAudience, "agents_public", "Agents publics")
        self.audience_citizens = get_or_create(TargetAudience, "citoyens", "Citoyens")
        self.audience_companies = get_or_create(TargetAudience, "entreprises", "Entreprises")
        self.offer_types = {
            slug: get_or_create(Offertype, slug, name)
            for slug, name in [("outil", "Outil"), ("financement", "Financement"), ("expertise", "Expertise")]
        }

        # Organization slugs are not unique, so look them up manually
        self.dinum = Organization.objects.filter(slug="dinum").first() or Organization.objects.create(
            name="DINUM", slug="dinum"
        )

    def get_or_create_page(self, parent: Page, page_class, slug: str, **fields) -> Page:
        already_exists = page_class.objects.child_of(parent).filter(slug=slug).first()
        if already_exists:
            self.stdout.write(f"The {slug} page already exists with id {already_exists.id}")
            return already_exists

        page = parent.add_child(instance=page_class(slug=slug, **fields))
        page.save_revision().publish()
        self.stdout.write(self.style.SUCCESS(f"Page {slug} created with id {page.id}"))
        return page

    def add_relations(self, page: Page, **relations) -> None:
        for field_name, values in relations.items():
            getattr(page, field_name).add(*values)
        page.save()

    def create_blog(self):
        self.blog_index = self.get_or_create_page(
            self.home, NumeriqueBlogIndexPage, "actualites", title="Actualités", show_in_menus=True
        )

        posts = [
            ("lancement-offre-ia", "Lancement de l’offre d’accompagnement IA", datetime(2025, 3, 12), "tag_ia"),
            ("nouvelle-strategie-cloud", "Nouvelle stratégie cloud de l’État", datetime(2025, 2, 4), "area_cloud"),
            ("ouverture-des-donnees", "Ouverture des données publiques", datetime(2025, 1, 20), "tag_data"),
            ("agenda-ia", "L’IA au service des agents publics", datetime(2024, 12, 2), "tag_ia"),
        ]
        for slug, title, date, category in posts:
            post = self.get_or_create_page(
                self.blog_index, NumeriqueBlogEntryPage, slug, title=title, date=date.replace(tzinfo=PARIS_TZ)
            )
            relations = {"organizations": [self.dinum]}
            if category == "area_cloud":
                relations["major_areas"] = [self.area_cloud]
            else:
                relations["page_tags"] = [getattr(self, category)]
            self.add_relations(post, **relations)

    def create_offers(self):
        self.offers_index = self.get_or_create_page(
            self.home, OffersIndexPage, "offre-accompagnement", title="Offre d’accompagnement", show_in_menus=True
        )

        offers = [
            ("albert", "Albert, l’IA des agents publics", "outil", 1, [self.tag_ia]),
            ("france-transfert", "France transfert", "outil", 2, [self.tag_data]),
            ("fonds-transformation", "Fonds pour la transformation de l’action publique", "financement", 1, []),
            ("conseil-ia", "Conseil en intelligence artificielle", "expertise", 1, [self.tag_ia]),
        ]
        for slug, title, type_slug, position, tags in offers:
            offer = self.get_or_create_page(
                self.offers_index,
                OffersEntryPage,
                slug,
                title=title,
                type=self.offer_types[type_slug],
                position=position,
                card_text=f"Découvrez {title}.",
            )
            self.add_relations(
                offer, page_tags=tags, target_audiences=[self.audience_agents], organizations=[self.dinum]
            )

    def create_products(self):
        self.products_index = self.get_or_create_page(
            self.home, ProductsIndexPage, "services-numeriques", title="Services numériques", show_in_menus=True
        )

        products = [
            ("proconnect", "ProConnect", [self.audience_agents], [self.tag_ia]),
            ("franceconnect", "FranceConnect", [self.audience_citizens], []),
            ("api-entreprise", "API Entreprise", [self.audience_companies], [self.tag_data]),
        ]
        for position, (slug, title, audiences, tags) in enumerate(products, start=1):
            product = self.get_or_create_page(
                self.products_index,
                ProductsEntryPage,
                slug,
                title=title,
                position=position,
                the_problem=f"Le problème résolu par {title}.",
                the_service=f"Le service proposé par {title}.",
            )
            self.add_relations(product, target_audiences=audiences, page_tags=tags)

    def create_hub(self):
        self.get_or_create_page(
            self.home,
            HubPages,
            "hub-intelligence-artificielle",
            title="Intelligence artificielle",
            content_source="page_tag",
            page_tag=self.tag_ia,
            introduction_text="Toutes les ressources sur l’intelligence artificielle.",
        )

    def create_sitemap(self):
        # SitemapPage can only be created under a NumeriquePage
        about = self.get_or_create_page(self.home, NumeriquePage, "a-propos-numerique", title="À propos")
        self.get_or_create_page(about, SitemapPage, "carte-du-site", title="Carte du site")
