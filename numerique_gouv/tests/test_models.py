from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from numerique_gouv.models import (
    HubPages,
    MajorArea,
    NumeriqueBlogEntryPage,
    NumeriqueBlogIndexPage,
    NumeriqueCatalogIndexPage,
    NumeriqueEventPage,
    NumeriqueEventsIndexPage,
    NumeriquePage,
    OffersEntryPage,
    OffersIndexPage,
    PageTag,
    ProductsEntryPage,
    ProductsIndexPage,
    SitemapPage,
)
from numerique_gouv.tests.base import NumeriqueTestCase


class BaseCategoryTestCase(NumeriqueTestCase):
    def test_str_returns_name(self):
        self.assertEqual(str(self.tag_ia), "Intelligence artificielle")
        self.assertEqual(str(self.area_cloud), "Cloud")


class NumeriquePageTestCase(NumeriqueTestCase):
    def setUp(self):
        super().setUp()
        self.page = self.add_page(self.home, NumeriquePage, title="Page numérique", slug="page-numerique")

    def test_page_is_renderable(self):
        self.assertPageIsRenderable(self.page)

    def test_page_has_title(self):
        response = self.client.get(self.page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<title>Page numérique — Titre du site</title>", html=True)


class OffersTestCase(NumeriqueTestCase):
    def setUp(self):
        super().setUp()
        self.index = self.add_page(self.home, OffersIndexPage, title="Offres", slug="offres")

        # Positions 0 are expected to be listed last
        self.tool_last = self.add_offer("Outil sans position", "outil", position=0)
        self.tool_second = self.add_offer("Outil 2", "outil", position=2)
        self.tool_first = self.add_offer("Outil 1", "outil", position=1)

        self.funding = self.add_offer("Financement", "financement", tags=[self.tag_ia])
        self.expertise = self.add_offer(
            "Expertise", "expertise", audiences=[self.audience_agents], organizations=[self.dinum]
        )
        self.steering = self.add_offer("Pilotage", "pilotage")
        self.observatory = self.add_offer("Observatoire", "observatoire")
        self.document = self.add_offer("Document", "document", tags=[self.tag_data])

        self.draft = self.add_offer("Offre brouillon", "outil", live=False, tags=[self.tag_unused])

    def add_offer(self, title, type_slug, tags=None, audiences=None, organizations=None, **kwargs):
        offer = self.add_page(self.index, OffersEntryPage, title=title, type=self.offer_types[type_slug], **kwargs)
        offer.page_tags.add(*(tags or []))
        offer.target_audiences.add(*(audiences or []))
        offer.organizations.add(*(organizations or []))
        offer.save()
        return offer

    def get_context(self, **params):
        response = self.client.get(self.index.url, params)
        self.assertEqual(response.status_code, 200)
        return response.context

    def test_index_is_renderable(self):
        self.assertPageIsRenderable(self.index)

    def test_offer_is_renderable(self):
        self.assertPageIsRenderable(self.funding)

    def test_offers_only_include_live_pages(self):
        self.assertNotIn(self.draft, self.index.offers)
        self.assertEqual(self.index.offers.count(), 8)

    def test_offers_are_split_by_type(self):
        context = self.get_context()
        self.assertEqual(list(context["financement_subpages"]), [self.funding])
        self.assertEqual(list(context["expertise_subpages"]), [self.expertise])
        self.assertCountEqual(list(context["pilotage_subpages"]), [self.steering, self.observatory])
        self.assertEqual(list(context["document_subpages"]), [self.document])
        self.assertEqual(len(context["all_subpages"]), 8)

    def test_offers_are_ordered_by_position_with_zero_last(self):
        context = self.get_context()
        self.assertEqual(list(context["tools_subpages"]), [self.tool_first, self.tool_second, self.tool_last])
        self.assertEqual(list(context["all_subpages"])[-1].position, 0)

    def test_filter_by_page_tag(self):
        context = self.get_context(page_tag="ia")
        self.assertEqual(list(context["offers"]), [self.funding])
        self.assertEqual(context["current_page_tag"], self.tag_ia)

    def test_filter_by_target_audience(self):
        context = self.get_context(target_audience="agents_public")
        self.assertEqual(list(context["offers"]), [self.expertise])
        self.assertEqual(context["current_target_audience"], self.audience_agents)

    def test_filter_by_organization(self):
        context = self.get_context(organization="dinum")
        self.assertEqual(list(context["offers"]), [self.expertise])
        self.assertEqual(context["current_organization"], self.dinum)

    def test_unknown_filter_returns_404(self):
        for param in ["page_tag", "target_audience", "organization"]:
            with self.subTest(param=param):
                response = self.client.get(self.index.url, {param: "inconnu"})
                self.assertEqual(response.status_code, 404)

    def test_filter_lists_only_contain_used_values(self):
        self.assertEqual(list(self.index.get_page_tags()), [self.tag_data, self.tag_ia])
        self.assertEqual(list(self.index.get_target_audiences()), [self.audience_agents])
        self.assertEqual(list(self.index.get_organizations()), [self.dinum])

    def test_offer_absolute_url(self):
        self.assertEqual(self.funding.get_absolute_url(), self.funding.url)


class ProductsTestCase(NumeriqueTestCase):
    def setUp(self):
        super().setUp()
        self.index = self.add_page(self.home, ProductsIndexPage, title="Services numériques", slug="services")

        self.agents_last = self.add_product("Produit agents sans position", [self.audience_agents], position=0)
        self.agents_second = self.add_product("Produit agents 2", [self.audience_agents], position=2)
        self.agents_first = self.add_product("Produit agents 1", [self.audience_agents], position=1)
        self.citizens = self.add_product("Produit citoyens", [self.audience_citizens])
        self.companies = self.add_product("Produit entreprises", [self.audience_companies, self.audience_citizens])
        self.draft = self.add_product("Produit brouillon", [self.audience_agents], live=False)

    def add_product(self, title, audiences, **kwargs):
        product = self.add_page(self.index, ProductsEntryPage, title=title, **kwargs)
        product.target_audiences.add(*audiences)
        product.save()
        return product

    def test_index_is_renderable(self):
        self.assertPageIsRenderable(self.index)

    def test_product_redirects_to_index(self):
        response = self.client.get(self.citizens.url)
        self.assertRedirects(response, self.index.url, fetch_redirect_response=False)

    def test_agents_subpages_are_filtered_and_ordered(self):
        self.assertEqual(
            list(self.index.get_agents_publics_subpages()),
            [self.agents_first, self.agents_second, self.agents_last],
        )

    def test_citizens_subpages(self):
        self.assertCountEqual(list(self.index.get_citizens_subpages()), [self.citizens, self.companies])

    def test_companies_subpages(self):
        self.assertEqual(list(self.index.get_companies_subpages()), [self.companies])

    def test_index_context(self):
        response = self.client.get(self.index.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["agents_publics_subpages"]), 3)
        self.assertEqual(len(response.context["citizens_subpages"]), 2)
        self.assertEqual(len(response.context["companies_subpages"]), 1)


class NumeriqueBlogTestCase(NumeriqueTestCase):
    def setUp(self):
        super().setUp()
        self.index = self.add_page(
            self.home, NumeriqueBlogIndexPage, title="Actualités", slug="actualites", posts_per_page=2
        )
        now = timezone.now()
        self.oldest = self.add_post("Article ancien", now - timedelta(days=30), tags=[self.tag_ia])
        self.middle = self.add_post("Article moyen", now - timedelta(days=10), areas=[self.area_cloud])
        self.newest = self.add_post("Article récent", now, organizations=[self.dinum])
        self.draft = self.add_post("Article brouillon", now, live=False, tags=[self.tag_unused])

    def add_post(self, title, date, tags=None, areas=None, organizations=None, **kwargs):
        post = self.add_page(self.index, NumeriqueBlogEntryPage, title=title, date=date, **kwargs)
        post.page_tags.add(*(tags or []))
        post.major_areas.add(*(areas or []))
        post.organizations.add(*(organizations or []))
        post.save()
        return post

    def get_context(self, **params):
        response = self.client.get(self.index.url, params)
        self.assertEqual(response.status_code, 200)
        return response.context

    def test_index_is_renderable(self):
        self.assertPageIsRenderable(self.index)

    def test_post_is_renderable(self):
        self.assertPageIsRenderable(self.newest)

    def test_post_has_title(self):
        response = self.client.get(self.newest.url)
        self.assertContains(response, "Article récent")

    def test_posts_are_live_and_ordered_by_date_desc(self):
        posts = self.get_context()["posts"]
        self.assertEqual(list(posts), [self.newest, self.middle])
        self.assertEqual(posts.paginator.count, 3)

    def test_pagination(self):
        self.assertEqual(list(self.get_context(page=2)["posts"]), [self.oldest])

    def test_invalid_page_falls_back_to_first_page(self):
        self.assertEqual(self.get_context(page="abc")["posts"].number, 1)

    def test_out_of_range_page_falls_back_to_last_page(self):
        self.assertEqual(self.get_context(page=999)["posts"].number, 2)

    def test_filter_by_page_tag(self):
        context = self.get_context(page_tag="ia")
        self.assertEqual(list(context["posts"]), [self.oldest])
        self.assertEqual(context["current_page_tag"], self.tag_ia)

    def test_filter_by_major_area(self):
        context = self.get_context(major_area="cloud")
        self.assertEqual(list(context["posts"]), [self.middle])
        self.assertEqual(context["current_major_area"], self.area_cloud)

    def test_filter_by_organization(self):
        context = self.get_context(organization="dinum")
        self.assertEqual(list(context["posts"]), [self.newest])
        self.assertEqual(context["current_organization"], self.dinum)

    def test_unknown_filter_returns_404(self):
        for param in ["page_tag", "major_area", "organization"]:
            with self.subTest(param=param):
                response = self.client.get(self.index.url, {param: "inconnu"})
                self.assertEqual(response.status_code, 404)

    def test_filter_lists_only_contain_used_values(self):
        self.assertEqual(list(self.index.get_page_tags()), [self.tag_ia])
        self.assertEqual(list(self.index.get_major_areas()), [self.area_cloud])
        self.assertEqual(list(self.index.get_organizations()), [self.dinum])


class HubPagesTestCase(NumeriqueTestCase):
    def setUp(self):
        super().setUp()
        self.blog_index = self.add_page(self.home, NumeriqueBlogIndexPage, title="Actualités", slug="actualites")
        self.offers_index = self.add_page(self.home, OffersIndexPage, title="Offres", slug="offres")
        self.products_index = self.add_page(self.home, ProductsIndexPage, title="Services", slug="services")

        self.posts = []
        for i in range(4):
            post = self.add_page(self.blog_index, NumeriqueBlogEntryPage, title=f"Article {i}")
            post.page_tags.add(self.tag_ia)
            post.major_areas.add(self.area_cloud)
            post.save()
            self.posts.append(post)
        self.untagged_post = self.add_page(self.blog_index, NumeriqueBlogEntryPage, title="Article sans tag")

        self.offer = self.add_page(self.offers_index, OffersEntryPage, title="Offre IA")
        self.offer.page_tags.add(self.tag_ia)
        self.offer.organizations.add(self.dinum)
        self.offer.save()

        self.product = self.add_page(self.products_index, ProductsEntryPage, title="Produit IA")
        self.product.page_tags.add(self.tag_ia)
        self.product.target_audiences.add(self.audience_agents)
        self.product.save()

        self.hub = self.add_page(
            self.home,
            HubPages,
            title="Hub IA",
            slug="hub-ia",
            content_source="page_tag",
            page_tag=self.tag_ia,
        )

    def test_hub_is_renderable(self):
        self.assertPageIsRenderable(self.hub)

    def test_get_entries_by_page_tag(self):
        news = list(self.hub.get_entries("blog"))
        # Only the 3 most recent (highest id) tagged posts
        self.assertEqual(news, list(reversed(self.posts[1:])))
        self.assertEqual(list(self.hub.get_entries("offers")), [self.offer])
        self.assertEqual(list(self.hub.get_entries("products")), [self.product])

    def test_get_entries_by_other_sources(self):
        cases = [
            ("major_area", {"major_area": self.area_cloud}, "blog", 3),
            ("organization", {"organization": self.dinum}, "offers", 1),
            ("target_audience", {"target_audience": self.audience_agents}, "products", 1),
            ("target_audience", {"target_audience": self.audience_citizens}, "products", 0),
        ]
        for content_source, fields, entry_type, expected_count in cases:
            with self.subTest(content_source=content_source, entry_type=entry_type):
                self.hub.content_source = content_source
                for name, value in fields.items():
                    setattr(self.hub, name, value)
                self.assertEqual(len(self.hub.get_entries(entry_type)), expected_count)

    def test_get_content_source_name(self):
        self.assertEqual(self.hub.get_content_source_name(), "intelligence artificielle")

        self.hub.content_source = "organization"
        self.hub.organization = self.dinum
        self.assertEqual(self.hub.get_content_source_name(), "dinum")

    def test_get_content_source_slug(self):
        self.assertEqual(self.hub.get_content_source_slug(), "ia")

        self.hub.content_source = "target_audience"
        self.hub.target_audience = self.audience_agents
        self.assertEqual(self.hub.get_content_source_slug(), "agents_public")

        self.hub.target_audience = None
        self.assertEqual(self.hub.get_content_source_slug(), "")

    def test_see_more_news_link_when_news_are_full(self):
        response = self.client.get(self.hub.url)
        self.assertContains(response, 'href="/actualites/?page_tag=ia"')

    def test_see_all_news_link_when_few_news(self):
        self.hub.content_source = "major_area"
        self.hub.major_area = self.area_unused
        self.hub.save()
        # No news at all: the news section is hidden
        response = self.client.get(self.hub.url)
        self.assertNotContains(response, "/actualites/?")

        self.posts[0].major_areas.add(self.area_unused)
        self.posts[0].save()
        response = self.client.get(self.hub.url)
        self.assertNotContains(response, "/actualites/?")
        self.assertContains(response, 'href="/actualites/"')

    def test_hub_context(self):
        response = self.client.get(self.hub.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["news"]), 3)
        self.assertEqual(list(response.context["offers"]), [self.offer])
        self.assertEqual(list(response.context["products"]), [self.product])
        self.assertContains(response, "Offre IA")


class NumeriqueEventsTestCase(NumeriqueTestCase):
    def setUp(self):
        super().setUp()
        self.index = self.add_page(self.home, NumeriqueEventsIndexPage, title="Agenda", slug="agenda")
        now = timezone.now()
        self.event = self.add_page(
            self.index,
            NumeriqueEventPage,
            title="Événement numérique",
            date=now,
            event_date_start=now + timedelta(days=10),
            event_date_end=now + timedelta(days=11),
        )

    def test_index_is_renderable(self):
        self.assertPageIsRenderable(self.index)

    def test_event_is_renderable(self):
        self.assertPageIsRenderable(self.event)

    def test_index_lists_event(self):
        response = self.client.get(self.index.url)
        self.assertContains(response, "Événement numérique")


class SitemapPageTestCase(NumeriqueTestCase):
    def setUp(self):
        super().setUp()
        self.section = self.add_page(self.home, NumeriquePage, title="Rubrique", slug="rubrique")
        self.subpage = self.add_page(self.section, NumeriquePage, title="Sous-page", slug="sous-page")
        self.draft = self.add_page(self.section, NumeriquePage, title="Page brouillon", slug="brouillon", live=False)
        self.sitemap = self.add_page(self.section, SitemapPage, title="Plan du site", slug="plan-du-site")

    def test_sitemap_is_renderable(self):
        self.assertPageIsRenderable(self.sitemap)

    def test_sitemap_lists_live_pages_only(self):
        response = self.client.get(self.sitemap.url)
        self.assertContains(response, "Rubrique")
        self.assertContains(response, "Sous-page")
        self.assertNotContains(response, "Page brouillon")

    def test_sitemap_structure(self):
        response = self.client.get(self.sitemap.url)
        structure = response.context["site_structure"]
        self.assertEqual(structure["page"], self.home.specific)
        section = next(child for child in structure["children"] if child["page"] == self.section)
        child_titles = [child["page"].title for child in section["children"]]
        self.assertIn("Sous-page", child_titles)
        self.assertNotIn("Page brouillon", child_titles)


class NumeriqueCatalogIndexPageTestCase(NumeriqueTestCase):
    def setUp(self):
        super().setUp()
        self.catalog = self.add_page(
            self.home, NumeriqueCatalogIndexPage, title="Catalogue", slug="catalogue", entries_per_page=2
        )
        self.entries = [
            self.add_page(self.catalog, NumeriquePage, title=f"Entrée {i}", slug=f"entree-{i}") for i in range(3)
        ]
        self.draft = self.add_page(self.catalog, NumeriquePage, title="Entrée brouillon", live=False)
        self.grandchild = self.add_page(self.entries[0], NumeriquePage, title="Petite-fille", slug="petite-fille")

    def test_catalog_is_renderable(self):
        self.assertPageIsRenderable(self.catalog)

    def test_entries_are_live_children_only(self):
        self.assertCountEqual(list(self.catalog.entries), self.entries)

    def test_pagination(self):
        response = self.client.get(self.catalog.url)
        self.assertEqual(response.context["paginator"].count, 3)
        self.assertEqual(len(response.context["entries"]), 2)

        response = self.client.get(self.catalog.url, {"page": 999})
        self.assertEqual(response.context["entries"].number, 2)

    def test_tag_filters_are_disabled(self):
        response = self.client.get(self.catalog.url)
        self.assertEqual(response.context["tags"], [])
        self.assertFalse(self.catalog.show_filters)


class CategorySnippetsTestCase(NumeriqueTestCase):
    def test_slugs_are_unique(self):
        for model in [PageTag, MajorArea]:
            with self.subTest(model=model.__name__), self.assertRaises(IntegrityError), transaction.atomic():
                model.objects.create(name="Doublon", slug="cloud" if model is MajorArea else "ia")
