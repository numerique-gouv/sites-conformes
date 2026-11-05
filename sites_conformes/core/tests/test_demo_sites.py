from io import StringIO
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase, override_settings
from wagtail.contrib.redirects.models import Redirect
from wagtail.images import get_image_model
from wagtail.models import Page, ReferenceIndex, Site

from sites_conformes.blog.models import Category, CategoryEntryPage, Organization, Person
from sites_conformes.core.services.demo_sites import DEFAULT_PASSWORD, create_demo_sites
from sites_conformes.core.tests.base import ClearSiteRootPathsCacheMixin, MonositeTestCase, MultisiteTestCase
from sites_conformes.events.models import CategoryEventEntryPage
from sites_conformes.menus.models import MainMenu


class DemoSitesTestsMixin:
    """
    Tests run in both configurations, as an example for the multisite tickets.
    """

    def get_page(self, site: Site, path: str) -> Page:
        page = site.root_page
        for slug in path.strip("/").split("/"):
            page = page.get_children().get(slug=slug)
        return page.specific

    def assertHostResponds(self, hostname: str, path: str, text: str):
        response = self.client.get(path, HTTP_HOST=hostname)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, text)

    def test_site_a_responds_in_french_and_english(self):
        self.assertHostResponds("site-a.localhost", "/", "Ministère des Lampadaires et des Planètes")
        self.assertHostResponds("site-a.localhost", "/en/", "Welcome to the Ministry of Street Lamps and Planets")
        self.assertHostResponds("site-a.localhost", "/le-ministere/nos-missions/", "Nos missions")
        self.assertHostResponds("site-a.localhost", "/en/the-ministry/our-missions/", "Our missions")

    def test_footer_warns_that_the_sites_are_fictional(self):
        for site in self.demo.sites.values():
            for path in ["/", "/en/"]:
                with self.subTest(site=site.hostname, path=path):
                    response = self.client.get(path, HTTP_HOST=site.hostname)
                    self.assertContains(response, "est une administration fictive")
                    self.assertContains(response, "sert uniquement au développement")

    def test_sites_have_a_language_selector(self):
        for site in self.demo.sites.values():
            for path, current in [("/", "fr"), ("/en/", "en")]:
                with self.subTest(site=site.hostname, path=path):
                    response = self.client.get(path, HTTP_HOST=site.hostname)
                    self.assertContains(response, "fr-translate__menu")
                    self.assertContains(response, 'hreflang="en"')
                    self.assertContains(response, f'lang="{current}"')

    def test_site_a_has_a_megamenu_with_two_columns(self):
        for path, texts in [
            ("/", ["Le ministère", "Découvrir le ministère", "Vos services", "Signaler une panne de réverbère"]),
            ("/en/", ["The ministry", "Discover the ministry", "Services", "Report a faulty street lamp"]),
        ]:
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_HOST="site-a.localhost")
                for text in texts:
                    self.assertContains(response, text)

        for menu in MainMenu.objects.filter(site=self.site_a):
            with self.subTest(locale=menu.locale.language_code):
                self.assertEqual([block.block_type for block in menu.items], ["megamenu", "link", "link"])
                columns = menu.items[0].value["columns"]
                self.assertEqual([len(column.value["links"]) for column in columns], [4, 4])

    def test_site_a_has_a_minister_biography(self):
        self.assertHostResponds("site-a.localhost", "/le-ministere/le-ministre/", "Luc Falotier")
        self.assertHostResponds("site-a.localhost", "/en/the-ministry/the-minister/", "Biography")

    def test_site_a_has_its_pages_snippets_and_menus(self):
        for path in ["actualites", "contact", "mentions-legales", "accessibilite"]:
            self.assertTrue(self.get_page(self.site_a, path).live)
        self.assertEqual(self.get_page(self.site_a, "actualites").get_children().count(), 10)
        self.assertEqual(MainMenu.objects.filter(site=self.site_a).count(), 2)

        news = Category.objects.get(slug="actualites")
        self.assertEqual(news.get_translation(self.site_a.root_page.get_translations().get().locale).name, "News")
        self.assertTrue(Organization.objects.filter(slug="commission-des-asteroides").exists())
        self.assertTrue(Person.objects.filter(name="Paul Verdier").exists())

    def test_site_a_page_permissions(self):
        home = self.site_a.root_page
        page = self.get_page(self.site_a, "le-ministere/nos-missions")
        page_en = page.get_translations().get()

        expectations = {
            "superadmin": (True, True),
            "admin-a": (True, True),
            "moderateur-a": (True, True),
            "editeur-a": (True, False),
        }
        for username, (can_edit, can_publish) in expectations.items():
            with self.subTest(username=username):
                user = self.users[username]
                for tested_page in [home, page, page_en]:
                    permissions = tested_page.permissions_for_user(user)
                    self.assertEqual(permissions.can_edit(), can_edit)
                    self.assertEqual(permissions.can_publish(), can_publish)

    def test_no_redirect_is_created(self):
        self.assertFalse(Redirect.objects.exists())

    def test_site_a_groups(self):
        names = set(Group.objects.filter(name__startswith="Ministère").values_list("name", flat=True))
        self.assertEqual(
            names,
            {
                "Ministère des Lampadaires et des Planètes – Administrateurs",
                "Ministère des Lampadaires et des Planètes – Modérateurs",
                "Ministère des Lampadaires et des Planètes – Éditeurs",
            },
        )

    def test_accounts_can_log_in(self):
        for username in self.users:
            with self.subTest(username=username):
                self.assertTrue(self.client.login(username=username, password=self.demo.password))
                response = self.client.get("/cms-admin/", HTTP_HOST="site-a.localhost")
                self.assertEqual(response.status_code, 200)
                self.client.logout()


@override_settings(DEBUG=True)
class LoadReferenceBaseTestCase(ClearSiteRootPathsCacheMixin, TestCase):
    """
    Checks that the reference bases load with the current models.

    To be replaced by the tests of the migrations of tickets 10 and 11: once these
    migrations exist, the fixtures only load from the commit they were exported from.
    """

    def get_demo_images(self):
        return get_image_model().objects.exclude(
            collection__name__in=["Pictogrammes DSFR", "Illustrations par défaut"]
        )

    def assertBaseLoads(self, site_keys: list, default_host: str, pages: int, users: set):
        call_command("load_reference_base", *site_keys, skip_migrate=True, stdout=StringIO())

        self.assertEqual(Site.objects.count(), len(site_keys))
        self.assertEqual(Site.objects.get(is_default_site=True).hostname, default_host)
        self.assertEqual(Page.objects.filter(depth__gt=1).count(), pages)
        self.assertEqual(set(get_user_model().objects.values_list("username", flat=True)), users)

        # Shared image, in both fixtures
        image = get_image_model().objects.get(title__startswith="Pleine lune")
        with image.file.open() as image_file:
            self.assertTrue(image_file.read(4))

        # Every demo image is used, which the admin knows from the reference index
        unused = [
            image.title for image in self.get_demo_images() if not ReferenceIndex.get_references_to(image).exists()
        ]
        self.assertEqual(unused, [])

        welcomes = {
            "a": ("site-a.localhost", "Welcome to the Ministry of Street Lamps and Planets"),
            "b": ("site-b.localhost", "Star Census Directorate"),
        }
        for site_key in site_keys:
            hostname, text = welcomes[site_key]
            self.assertContains(self.client.get("/", HTTP_HOST=hostname), "Accueil")
            self.assertContains(self.client.get("/en/", HTTP_HOST=hostname), text)

    def test_site_a_loads_alone(self):
        self.assertBaseLoads(
            ["a"], "site-a.localhost", pages=50, users={"superadmin", "admin-a", "moderateur-a", "editeur-a"}
        )

    def test_site_b_loads_alone_as_the_default_site(self):
        self.assertBaseLoads(
            ["b"], "site-b.localhost", pages=33, users={"superadmin", "admin-b", "moderateur-b", "editeur-b"}
        )

    def test_both_sites_load_together(self):
        self.assertBaseLoads(
            ["a", "b"],
            "site-a.localhost",
            pages=83,
            users={
                "superadmin",
                "admin-a",
                "moderateur-a",
                "editeur-a",
                "admin-b",
                "moderateur-b",
                "editeur-b",
                "editeur-ab",
            },
        )
        # Every demo image is displayed somewhere, not only referenced by a field that no template shows.
        # The portrait of Paul Verdier is the exception: on purpose, no site uses this person.
        html = ""
        for page in Page.objects.live().filter(depth__gt=1).specific():
            _site_id, root_url, path = page.get_url_parts()
            response = self.client.get(path, HTTP_HOST=urlparse(root_url).hostname)
            self.assertEqual(response.status_code, 200, path)
            # Not the <head>, whose social media tags also use the legacy header image
            html += response.content.decode().split("<body", 1)[1]

        not_displayed = [
            image.title
            for image in self.get_demo_images()
            if Path(image.file.name).stem[:20] not in html  # Renditions keep the start of the file name
        ]
        self.assertEqual(not_displayed, ["Portrait de Paul Verdier"])

        # Not in the fixtures, as it belongs to both sites
        editeur_ab = get_user_model().objects.get(username="editeur-ab")
        self.assertEqual(editeur_ab.groups.filter(name__endswith="– Éditeurs").count(), 2)
        self.assertTrue(self.client.login(username="editeur-ab", password=DEFAULT_PASSWORD))

    @override_settings(HOST_PORT="8000")
    def test_sites_use_the_port_of_the_instance(self):
        # The fixtures contain a fixed port, not the one of the machine they were exported from
        call_command("load_reference_base", "a", "b", skip_migrate=True, stdout=StringIO())

        self.assertEqual(set(Site.objects.values_list("port", flat=True)), {8000})
        home = Site.objects.get(hostname="site-a.localhost").root_page
        _site_id, root_url, _path = home.get_url_parts()
        self.assertEqual(root_url, "http://site-a.localhost:8000")


class MonositeBDemoSitesTestCase(ClearSiteRootPathsCacheMixin, TestCase):
    def test_site_b_alone_is_the_default_site(self):
        demo = create_demo_sites(site_keys=("b",), with_media=False)

        self.assertEqual(list(demo.sites), ["b"])
        self.assertTrue(demo.sites["b"].is_default_site)
        self.assertEqual(Site.objects.count(), 1)
        self.assertEqual(set(demo.users), {"superadmin", "admin-b", "moderateur-b", "editeur-b"})
        self.assertContains(self.client.get("/", HTTP_HOST="site-b.localhost"), "Direction générale")


class MonositeDemoSitesTestCase(DemoSitesTestsMixin, MonositeTestCase):
    def test_isolation_is_disabled(self):
        self.assertFalse(settings.SF_MULTISITE_ISOLATION_ENABLED)

    def test_only_site_a_exists(self):
        self.assertEqual(Site.objects.count(), 1)
        self.assertEqual(set(self.users), {"superadmin", "admin-a", "moderateur-a", "editeur-a"})


class MultisiteDemoSitesTestCase(DemoSitesTestsMixin, MultisiteTestCase):
    def test_isolation_is_enabled(self):
        self.assertTrue(settings.SF_MULTISITE_ISOLATION_ENABLED)

    def test_site_b_responds(self):
        self.assertHostResponds("site-b.localhost", "/", "Direction générale du Recensement des étoiles")
        self.assertHostResponds("site-b.localhost", "/en/", "Star Census Directorate")
        self.assertHostResponds("site-b.localhost", "/demarches/par-planete/fiche-mars/", "Fiche : Mars")

    def test_site_b_has_submenus_and_a_minister_biography(self):
        menus = {menu.locale.language_code: menu for menu in MainMenu.objects.filter(site=self.site_b)}
        self.assertEqual([block.block_type for block in menus["fr"].items], ["submenu", "link", "link", "submenu"])
        self.assertEqual([len(block.value["links"]) for block in menus["fr"].items[::3]], [6, 3])
        # Only the translated pages are in the English menu
        self.assertEqual([block.value["label"] for block in menus["en"].items], ["Procedures", "About us"])

        self.assertHostResponds("site-b.localhost", "/", "Nous connaître")
        self.assertHostResponds("site-b.localhost", "/la-ministre/", "Najma Al-Biruni")
        self.assertHostResponds("site-b.localhost", "/en/the-minister/", "Minister Delegate for the Star Census")

    def test_sites_have_different_trees(self):
        self.assertTrue(self.get_page(self.site_b, "demarches/par-planete/fiche-mars"))
        self.assertFalse(self.site_a.root_page.get_children().filter(slug="demarches").exists())
        self.assertEqual(self.get_page(self.site_b, "agenda").get_children().count(), 10)

    def test_common_elements_exist_on_both_sites(self):
        for path in ["actualites", "contact", "mentions-legales", "accessibilite"]:
            with self.subTest(path=path):
                self.assertNotEqual(self.get_page(self.site_a, path).pk, self.get_page(self.site_b, path).pk)

        # The same category, organization and person are used by both sites
        news = Category.objects.get(slug="actualites")
        camille = Person.objects.get(name="Camille Roux")
        for site in [self.site_a, self.site_b]:
            with self.subTest(site=site.hostname):
                entries = self.get_page(site, "actualites").get_children().specific()
                self.assertTrue(any(news in entry.blog_categories.all() for entry in entries))
                self.assertTrue(any(camille in entry.authors.all() for entry in entries))

    def test_unused_snippets_exist(self):
        self.assertFalse(CategoryEntryPage.objects.filter(category__slug="archives").exists())
        self.assertFalse(CategoryEventEntryPage.objects.filter(category__slug="archives").exists())

        paul = Person.objects.get(name="Paul Verdier")
        self.assertFalse(paul.blogentrypage_set.exists())
        self.assertFalse(paul.evententrypage_set.exists())
        self.assertFalse(Person.objects.filter(organization__slug="commission-des-asteroides").exclude(pk=paul.pk))

    def test_page_permissions_are_limited_to_the_site(self):
        page_a = self.get_page(self.site_a, "contact")
        page_b = self.get_page(self.site_b, "contact")

        expectations = {
            "editeur-a": (True, False),
            "moderateur-b": (False, True),
            "editeur-ab": (True, True),
            "superadmin": (True, True),
        }
        for username, (can_edit_a, can_edit_b) in expectations.items():
            with self.subTest(username=username):
                user = self.users[username]
                self.assertEqual(page_a.permissions_for_user(user).can_edit(), can_edit_a)
                self.assertEqual(page_b.permissions_for_user(user).can_edit(), can_edit_b)

    def test_each_site_has_its_workflow(self):
        self.assertEqual(self.get_page(self.site_a, "contact").get_workflow().name, "Validation Lampadaires")
        self.assertEqual(
            self.get_page(self.site_b, "contact").get_workflow().name, "Validation Recensement des étoiles"
        )
