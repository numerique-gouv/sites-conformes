from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import RequestFactory, override_settings
from django.urls import reverse
from wagtail.models import Page, Site

from sites_conformes.core.multisite_isolation import (
    MIDDLEWARE_PATH,
    check_multisite_isolation_middleware,
    get_pages_in_scope_filter,
    is_page_in_scope,
)
from sites_conformes.core.services.demo_sites import get_permission
from sites_conformes.core.tests.base import MonositeTestCase, MultisiteTestCase
from sites_conformes.core.wagtail_hooks import restrict_page_chooser_to_user_sites


class PageScopeTestCase(MultisiteTestCase):
    def get_page(self, site: Site, path: str) -> Page:
        page = site.root_page
        for slug in path.strip("/").split("/"):
            page = page.get_children().get(slug=slug)
        return page

    def assertFilterMatchesPages(self, sites):
        expected = {page.pk for page in Page.objects.all() if is_page_in_scope(page, sites)}
        self.assertEqual(
            set(Page.objects.filter(get_pages_in_scope_filter(sites)).values_list("pk", flat=True)), expected
        )

    def test_pages_of_site_a(self):
        home_en = self.site_a.root_page.get_translations().get()
        for page in [
            Page.get_first_root_node(),
            self.site_a.root_page,
            self.get_page(self.site_a, "le-ministere/nos-missions"),
            home_en,
            home_en.get_children().first(),
        ]:
            with self.subTest(page=page.title):
                self.assertTrue(is_page_in_scope(page, [self.site_a]))

        for page in [self.site_b.root_page, self.site_b.root_page.get_children().first()]:
            with self.subTest(page=page.title):
                self.assertFalse(is_page_in_scope(page, [self.site_a]))
        self.assertFilterMatchesPages([self.site_a])

    def test_pages_outside_of_every_site(self):
        orphan = Page.get_first_root_node().add_child(instance=Page(title="Orpheline", slug="orpheline"))
        self.assertFalse(is_page_in_scope(orphan, [self.site_a, self.site_b]))
        self.assertFilterMatchesPages([self.site_a, self.site_b])

    def test_no_page_without_site(self):
        self.assertFalse(is_page_in_scope(Page.get_first_root_node(), []))
        self.assertFalse(Page.objects.filter(get_pages_in_scope_filter([])).exists())

    def test_pages_of_a_nested_site(self):
        ministry = self.get_page(self.site_a, "le-ministere")
        nested = Site.objects.create(hostname="ministere.site-a.localhost", port=self.site_a.port, root_page=ministry)
        missions = self.get_page(self.site_a, "le-ministere/nos-missions")

        self.assertFalse(is_page_in_scope(missions, [self.site_a]))
        self.assertTrue(is_page_in_scope(self.get_page(self.site_a, "contact"), [self.site_a]))
        self.assertTrue(is_page_in_scope(missions, [self.site_a, nested]))
        self.assertTrue(is_page_in_scope(missions, [nested]))
        self.assertFilterMatchesPages([self.site_a])
        self.assertFilterMatchesPages([nested])


class PageChooserAndExplorerTestsMixin:
    def login(self, username: str):
        user = self.users[username]
        self.client.force_login(user)
        return user

    def browse(self, page: Page | None = None):
        url = (
            reverse("wagtailadmin_choose_page_child", args=[page.pk]) if page else reverse("wagtailadmin_choose_page")
        )
        return self.client.get(url)

    def search(self, query: str) -> str:
        response = self.client.get(reverse("wagtailadmin_choose_page_search"), {"q": query})
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def browse_html(self, page: Page | None = None) -> str:
        response = self.browse(page)
        self.assertEqual(response.status_code, 200)
        return response.json()["html"]

    @staticmethod
    def choice(page: Page) -> str:
        return f'data-id="{page.pk}"'


class MonositePageChooserTestCase(PageChooserAndExplorerTestsMixin, MonositeTestCase):
    def test_chooser_is_not_restricted(self):
        request = RequestFactory().get("/")
        request.user = self.users["editeur-a"]
        pages = Page.objects.all()
        self.assertIs(restrict_page_chooser_to_user_sites(pages, request), pages)

    def test_explorer_is_unchanged(self):
        self.login("editeur-a")
        response = self.client.get(reverse("wagtailadmin_explore", args=[self.site_a.root_page.pk]))
        self.assertEqual(response.status_code, 200)


class MultisitePageChooserTestCase(PageChooserAndExplorerTestsMixin, MultisiteTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        root = Page.get_first_root_node()
        cls.home_c = root.add_child(instance=Page(title="Accueil du site C", slug="accueil-c"))
        cls.home_c.add_child(instance=Page(title="Page lumineuse du site C", slug="page-c"))
        cls.site_c = Site.objects.create(hostname="site-c.localhost", root_page=cls.home_c, site_name="Site C")

    def get_page_only_in_site_b(self) -> Page:
        titles_a = set(Page.objects.descendant_of(self.site_a.root_page).values_list("title", flat=True))
        return next(
            page
            for page in self.site_b.root_page.get_descendants().specific()
            if page.title not in titles_a and len(page.title.split()) > 1
        )

    def test_browsing_only_shows_the_sites_of_the_editor(self):
        self.login("editeur-a")
        html = self.browse_html()
        self.assertIn(self.choice(self.site_a.root_page), html)
        self.assertIn(self.choice(self.site_a.root_page.get_translations().get()), html)
        self.assertNotIn(self.choice(self.site_b.root_page), html)
        self.assertNotIn(self.choice(self.home_c), html)

    def test_browsing_a_page_of_site_b_opens_the_root(self):
        self.login("editeur-a")
        page = self.site_b.root_page.get_children().first()
        response = self.client.get(
            reverse("wagtailadmin_choose_page_child", args=[page.pk]), {"page_type": "wagtailcore.page"}
        )
        self.assertRedirects(response, reverse("wagtailadmin_choose_page") + "?page_type=wagtailcore.page")

        self.assertIn(
            self.choice(self.site_a.root_page.get_children().first()), self.browse_html(self.site_a.root_page)
        )

    def test_search_finds_no_page_of_site_b(self):
        page_b = self.get_page_only_in_site_b()

        self.login("editeur-b")
        self.assertIn(page_b.title, self.search(page_b.title))

        self.login("editeur-a")
        self.assertNotIn(page_b.title, self.search(page_b.title))

    def test_search_of_the_editor_of_sites_a_and_b(self):
        self.login("editeur-ab")
        page_b = self.get_page_only_in_site_b()
        self.assertIn(page_b.title, self.search(page_b.title))
        self.assertNotIn("Page lumineuse du site C", self.search("lumineuse"))

        html = self.browse_html()
        self.assertIn(self.choice(self.site_a.root_page), html)
        self.assertIn(self.choice(self.site_b.root_page), html)
        self.assertNotIn(self.choice(self.home_c), html)

    def test_superadmin_finds_every_page(self):
        self.login("superadmin")
        self.assertIn("Page lumineuse du site C", self.search("lumineuse"))
        self.assertIn(self.choice(self.home_c), self.browse_html())

    def test_explorer_shows_nothing_of_site_b(self):
        page_b = self.get_page_only_in_site_b()
        self.login("editeur-a")
        for page in [self.site_b.root_page, page_b.get_parent(), page_b]:
            for name in ["wagtailadmin_explore", "wagtailadmin_explore_results"]:
                with self.subTest(page=page.title, view=name):
                    response = self.client.get(reverse(name, args=[page.pk]))
                    self.assertEqual(response.status_code, 404)
                    self.assertNotContains(response, page_b.title, status_code=404)
                    self.assertNotContains(response, self.site_b.site_name, status_code=404)

        response = self.client.get(reverse("wagtailadmin_explore", args=[self.site_a.root_page.pk]))
        self.assertEqual(response.status_code, 200)

    def test_explorer_of_the_editor_of_sites_a_and_b(self):
        self.login("editeur-ab")
        self.assertEqual(
            self.client.get(reverse("wagtailadmin_explore", args=[self.site_b.root_page.pk])).status_code, 200
        )
        response = self.client.get(reverse("wagtailadmin_explore", args=[self.home_c.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, self.home_c.title, status_code=404)


class MultisiteIsolationMiddlewareCheckTestCase(MultisiteTestCase):
    def test_no_message_with_the_middleware(self):
        self.assertIn(MIDDLEWARE_PATH, settings.MIDDLEWARE)
        self.assertEqual(check_multisite_isolation_middleware(), [])

    def test_message_without_the_middleware(self):
        with override_settings(MIDDLEWARE=[path for path in settings.MIDDLEWARE if path != MIDDLEWARE_PATH]):
            self.assertEqual(
                [message.id for message in check_multisite_isolation_middleware()], ["sites_conformes_core.W002"]
            )

    @override_settings(SF_MULTISITE_ISOLATION_ENABLED=False)
    def test_no_message_with_the_isolation_disabled(self):
        with override_settings(MIDDLEWARE=[path for path in settings.MIDDLEWARE if path != MIDDLEWARE_PATH]):
            self.assertEqual(check_multisite_isolation_middleware(), [])


class MultisiteIsolationReportTestCase(MultisiteTestCase):
    def call_command(self) -> str:
        out = StringIO()
        call_command("multisite_isolation_report", stdout=out)
        return out.getvalue()

    def test_every_group_has_page_permissions(self):
        output = self.call_command()
        self.assertIn("Multisite isolation: enabled", output)
        self.assertIn("sites_conformes_menus.MainMenu", output)
        self.assertIn("Every group with permissions on these models has page permissions.", output)

    def test_groups_without_page_permission(self):
        group = Group.objects.create(name="Menus seulement")
        group.permissions.add(get_permission("sites_conformes_menus.change_topmenu"))
        get_user_model().objects.create(username="menus-seulement").groups.add(group)
        Group.objects.create(name="Groupe vide").permissions.add(get_permission("sites_conformes_menus.view_mainmenu"))

        output = self.call_command()
        self.assertIn("2 group(s) without page permission:", output)
        self.assertIn("- Menus seulement\n  Models: sites_conformes_menus.TopMenu\n  Members: menus-seulement", output)
        self.assertIn("- Groupe vide\n  Models: sites_conformes_menus.MainMenu\n  Members: none", output)
