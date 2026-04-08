from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from content_manager.models import (
    CatalogIndexPage,
    CmsDsfrConfig,
    ContentPage,
    Tag,
)
from content_manager.services.accessors import get_or_create_content_page

User = get_user_model()


class ContentPageTestCase(WagtailPageTestCase):
    def setUp(self):
        home_page = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()
        self.public_content_page = home_page.add_child(
            instance=ContentPage(
                title="Page de contenu publique",
                slug="public-content-page",
                owner=self.admin,
            )
        )
        self.public_content_page.save()
        self.private_content_page = get_or_create_content_page(
            "private-content-page",
            title="Page de contenu privée",
            body=[("subpageslist", None)],
            parent_page=home_page,
            restriction_type="login",
        )
        self.private_content_page.save()

    def test_content_page_is_renderable(self):
        self.assertPageIsRenderable(self.public_content_page)

    def test_content_page_has_minimal_content(self):
        response = self.client.get(self.public_content_page.url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "<title>Page de contenu publique — Titre du site</title>",
        )

    def test_public_content_page_is_in_the_site_map(self):
        url = reverse("readable_sitemap")
        response = self.client.get(url)

        self.assertContains(
            response,
            """<a href="/public-content-page/">Page de contenu publique</a>""",
        )

    def test_private_content_page_is_not_rendered_when_logged_out(self):
        response = self.client.get(self.private_content_page.url)
        self.assertEqual(response.status_code, 302)

    def test_private_content_page_is_not_in_the_site_map_when_logged_out(self):
        url = reverse("readable_sitemap")
        response = self.client.get(url)

        self.assertNotContains(
            response,
            """<a href="/private-content-page/">Page de contenu privée</a>""",
        )

    def test_private_content_page_is_in_the_site_map_when_logged_in(self):
        self.client.login(username="test", password="pass")
        url = reverse("readable_sitemap")
        response = self.client.get(url)

        self.assertContains(
            response,
            """<a href="/private-content-page/">Page de contenu privée</a>""",
        )


class ConfigTestCase(WagtailPageTestCase):
    def setUp(self):
        home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()
        self.content_page = home.add_child(
            instance=ContentPage(
                title="Page de contenu",
                slug="content-page",
                owner=self.admin,
            )
        )
        self.content_page.save()

        self.config, _created = CmsDsfrConfig.objects.update_or_create(
            site_id=1,
            defaults={
                "site_title": "Site title",
                "site_tagline": "Site tagline",
                "header_brand": "République française",
                "header_brand_html": "République<br />française",
                "footer_brand": "République française",
                "footer_brand_html": "République<br />française",
                "footer_description": "Site <b>description</b>.",
            },
        )
        self.config.save()

    def test_header_brand_block_uses_conf(self):
        url = self.content_page.url
        response = self.client.get(url)

        self.assertInHTML(
            """<p class="fr-logo">République<br />française</p>""",
            response.content.decode(),
        )

    def test_footer_brand_block_uses_conf(self):
        url = self.content_page.url
        response = self.client.get(url)

        self.assertInHTML(
            """<div class="fr-footer__brand fr-enlarge-link">
                    <a id="footer-operator"
                    href="/"
                    title="Retourner à l’accueil - Site title - République française">
                    <p class="fr-logo">
                        République<br />française
                    </p>
                </a>
            </div>""",
            response.content.decode(),
        )

    def test_header_title_block_uses_conf(self):
        url = self.content_page.url
        response = self.client.get(url)

        self.assertInHTML(
            """<div class="fr-header__service">
                <a href="/" title="Accueil — Site title">
                    <p class="fr-header__service-title">Site title</p>
                </a>
                <p class="fr-header__service-tagline">Site tagline</p>
            </div>""",
            response.content.decode(),
        )

    def test_notice_is_not_set_by_default(self):
        url = self.content_page.url
        response = self.client.get(url)

        self.assertNotContains(
            response,
            "fr-notice__body",
        )

    def test_notice_can_be_set(self):
        self.config.notice_title = "Ceci est une information <b>importante</b> et <i>temporaire</i>."
        self.config.save()

        url = self.content_page.url
        response = self.client.get(url)

        self.assertContains(response, self.config.notice_title)

    def test_beta_tag_is_not_set_by_default(self):
        url = self.content_page.url
        response = self.client.get(url)

        self.assertNotContains(
            response,
            '<span class="fr-badge fr-badge--sm fr-badge--green-emeraude">BETA</span>',
        )

    def test_beta_tag_can_be_set(self):
        self.config.beta_tag = True
        self.config.save()

        url = self.content_page.url
        response = self.client.get(url)

        self.assertContains(
            response,
            '<span class="fr-badge fr-badge--sm fr-badge--green-emeraude">BETA</span>',
        )

    def test_footer_description_uses_conf(self):
        url = self.content_page.url
        response = self.client.get(url)

        self.config.refresh_from_db()

        self.assertContains(response, self.config.footer_description)


class CatalogIndexPageTestCase(WagtailPageTestCase):
    def setUp(self):
        home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()
        self.catalog_index_page = home.add_child(
            instance=CatalogIndexPage(
                title="Index de catalogue",
                slug="catalog-index",
                owner=self.admin,
            )
        )
        self.catalog_index_page.save()

        # Create tags
        self.tag1 = Tag.objects.create(name="Tag 1", slug="tag-1")
        self.tag2 = Tag.objects.create(name="Tag 2", slug="tag-2")

        # Create entries
        self.entry1 = self.catalog_index_page.add_child(
            instance=ContentPage(title="Entrée 1", slug="entry-1", owner=self.admin)
        )
        self.entry1.tags.add(self.tag1)
        self.entry1.save()

        self.entry2 = self.catalog_index_page.add_child(
            instance=ContentPage(title="Entrée 2", slug="entry-2", owner=self.admin)
        )
        self.entry2.tags.add(self.tag2)
        self.entry2.save()

        self.entry3 = self.catalog_index_page.add_child(
            instance=ContentPage(title="Entrée 3", slug="entry-3", owner=self.admin)
        )
        self.entry3.tags.add(self.tag1, self.tag2)
        self.entry3.save()

        self.entry4 = self.catalog_index_page.add_child(
            instance=ContentPage(title="Entrée 4", slug="entry-4", owner=self.admin)
        )
        self.entry4.save()

    def test_catalog_index_page_is_renderable(self):
        self.assertPageIsRenderable(self.catalog_index_page)

    def test_catalog_index_page_has_minimal_content(self):
        url = self.catalog_index_page.url
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertInHTML(
            "<title>Index de catalogue — Titre du site</title>",
            response.content.decode(),
        )

        self.assertContains(response, "Entrée 1")
        self.assertContains(response, "Entrée 2")
        self.assertContains(response, "Entrée 3")
        self.assertContains(response, "Entrée 4")

    def test_single_filter(self):
        self.catalog_index_page.filter_selection = CatalogIndexPage.SINGLE_FILTER
        self.catalog_index_page.save()

        url = self.catalog_index_page.url + "?tag=tag-1"
        response = self.client.get(url)

        self.assertContains(response, "Entrée 1")
        self.assertNotContains(response, "Entrée 2")
        self.assertContains(response, "Entrée 3")
        self.assertNotContains(response, "Entrée 4")

    def test_multiple_filter_and(self):
        self.catalog_index_page.filter_selection = CatalogIndexPage.MULTIPLE_FILTERS
        self.catalog_index_page.multiple_filter_operator = CatalogIndexPage.AND_OPERATOR
        self.catalog_index_page.save()

        url = self.catalog_index_page.url + "?tag=tag-1&tag=tag-2"
        response = self.client.get(url)

        self.assertNotContains(response, "Entrée 1")
        self.assertNotContains(response, "Entrée 2")
        self.assertContains(response, "Entrée 3")
        self.assertNotContains(response, "Entrée 4")

    def test_multiple_filter_or(self):
        self.catalog_index_page.filter_selection = CatalogIndexPage.MULTIPLE_FILTERS
        self.catalog_index_page.multiple_filter_operator = CatalogIndexPage.OR_OPERATOR
        self.catalog_index_page.save()

        url = self.catalog_index_page.url + "?tag=tag-1&tag=tag-2"
        response = self.client.get(url)

        self.assertContains(response, "Entrée 1")
        self.assertContains(response, "Entrée 2")
        self.assertContains(response, "Entrée 3")
        self.assertNotContains(response, "Entrée 4")

    def test_no_filter(self):
        url = self.catalog_index_page.url
        response = self.client.get(url)

        self.assertContains(response, "Entrée 1")
        self.assertContains(response, "Entrée 2")
        self.assertContains(response, "Entrée 3")
        self.assertContains(response, "Entrée 4")


class ErrorPagesTestCase(TestCase):
    def test_404_error_page(self):
        response = self.client.get("/404/")
        self.assertEqual(response.status_code, 404)
        self.assertInHTML(
            "<title>Erreur 404 — Page non trouvée — Titre du site</title>",
            response.content.decode(),
        )

    def test_500_error_page(self):
        response = self.client.get("/500/")
        self.assertEqual(response.status_code, 500)
        # Site settings are not available in a error 500 page so the site title is not there
        self.assertInHTML(
            "<title>Erreur 500 — Erreur inattendue</title>",
            response.content.decode(),
        )
