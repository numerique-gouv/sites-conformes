from html import unescape

from django.contrib.auth.models import Permission
from django.contrib.messages import get_messages
from django.test import RequestFactory
from django.urls import reverse
from wagtail.admin.menu import admin_menu
from wagtail.models import Locale, Site
from wagtail.test.utils.form_data import inline_formset, nested_form_data, streamfield

from sites_conformes.blog.models import BlogEntryPage, BlogIndexPage
from sites_conformes.core.models import Tag
from sites_conformes.core.tests.base import MonositeTestCase, MultisiteTestCase
from sites_conformes.proconnect.models import WhitelistedEmailDomain

# All the permissions on the shared snippets, given to the editors of site A:
# with the isolation, they must not give access to them
SHARED_SNIPPET_PERMISSIONS = {
    "sites_conformes_core": ["add_tag", "change_tag", "delete_tag", "view_tag"],
    "sites_conformes_proconnect": [
        "add_whitelistedemaildomain",
        "change_whitelistedemaildomain",
        "delete_whitelistedemaildomain",
        "view_whitelistedemaildomain",
    ],
}


class SharedSnippetsTestsMixin:
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.tag = Tag.objects.create(name="Lampadaires", slug="lampadaires")
        cls.domain = WhitelistedEmailDomain.objects.create(domain="lampadaires.gouv.fr")

        editors = cls.users["editeur-a"].groups.get()
        for app_label, codenames in SHARED_SNIPPET_PERMISSIONS.items():
            editors.permissions.add(
                *Permission.objects.filter(content_type__app_label=app_label, codename__in=codenames)
            )

    def get_snippet_urls(self) -> dict:
        return {
            "tags list": reverse("wagtailsnippets_sites_conformes_core_tag:list"),
            "tag creation": reverse("wagtailsnippets_sites_conformes_core_tag:add"),
            "tag edition": reverse("wagtailsnippets_sites_conformes_core_tag:edit", args=[self.tag.pk]),
            "tag deletion": reverse("wagtailsnippets_sites_conformes_core_tag:delete", args=[self.tag.pk]),
            "tag chooser": reverse("wagtailsnippetchoosers_sites_conformes_core_tag:choose"),
            "tag bulk deletion": reverse("wagtail_bulk_action", args=["sites_conformes_core", "tag", "delete"])
            + f"?id={self.tag.pk}",
            "domains list": reverse("member_views:list"),
            "domain creation": reverse("member_views:add"),
            "domain edition": reverse("member_views:edit", args=[self.domain.pk]),
            "domain chooser": reverse(
                "wagtailsnippetchoosers_sites_conformes_proconnect_whitelistedemaildomain:choose"
            ),
        }

    def assertAccessDenied(self, url: str):
        response = self.client.get(url)

        self.assertRedirects(response, reverse("wagtailadmin_home"), fetch_redirect_response=False)
        # The messages of the previous requests stay in the session, not shown
        message = list(get_messages(response.wsgi_request))[-1]
        self.assertEqual(
            unescape(message.message).strip(), "Désolé, vous n'avez pas les autorisations pour accéder à cette zone."
        )

    def get_menu_item_names(self, user) -> set:
        request = RequestFactory().get("/admin/")
        request.user = user
        return {item.name for item in admin_menu.menu_items_for_request(request)}

    def get_snippet_model_names(self, user) -> set:
        self.client.force_login(user)
        response = self.client.get(reverse("wagtailsnippets:index"))
        if response.status_code != 200:
            return set()
        return {snippet_type["model"]._meta.model_name for snippet_type in response.context["view"].snippet_types}

    def create_blog_entry(self, user, site: Site, locale: str, title: str, tags: str) -> BlogEntryPage:
        root_page = site.root_page.get_translation(Locale.objects.get(language_code=locale))
        parent = BlogIndexPage.objects.descendant_of(root_page).get()
        self.client.force_login(user)
        data = nested_form_data(
            {
                "title": title,
                "slug": title.lower().replace(" ", "-"),
                "hero": streamfield([]),
                "body": streamfield([]),
                "comments": inline_formset([]),
                "date": "2026-11-25 10:00",
                "tags": tags,
            }
        )
        response = self.client.post(
            reverse("wagtailadmin_pages:add", args=["sites_conformes_blog", "blogentrypage", parent.pk]), data
        )
        self.assertEqual(response.status_code, 302)
        return BlogEntryPage.objects.child_of(parent).get(title=title)

    def test_superuser_manages_the_shared_snippets(self):
        superuser = self.users["superadmin"]
        self.client.force_login(superuser)

        for name, url in self.get_snippet_urls().items():
            with self.subTest(name):
                self.assertEqual(self.client.get(url).status_code, 200)

        self.assertTrue({"snippets", "proconnect"} <= self.get_menu_item_names(superuser))
        self.assertIn("tag", self.get_snippet_model_names(superuser))

        response = self.client.post(
            reverse("wagtailsnippets_sites_conformes_core_tag:edit", args=[self.tag.pk]),
            {"name": "Lampadaires et réverbères", "slug": "lampadaires"},
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            reverse("member_views:edit", args=[self.domain.pk]), {"domain": "planetes.gouv.fr"}
        )
        self.assertEqual(response.status_code, 302)

        self.tag.refresh_from_db()
        self.domain.refresh_from_db()
        self.assertEqual(self.tag.name, "Lampadaires et réverbères")
        self.assertEqual(self.domain.domain, "planetes.gouv.fr")

    def test_editor_gets_tag_suggestions(self):
        self.client.force_login(self.users["editeur-a"])

        response = self.client.get(reverse("wagtailadmin_tag_autocomplete"), {"term": "lamp"})

        self.assertEqual(response.json(), ["Lampadaires"])

    def test_editor_chooses_tags_on_a_blog_entry(self):
        editor = self.users["editeur-a"]

        for locale in ["fr", "en"]:
            with self.subTest(locale):
                entry = self.create_blog_entry(editor, self.site_a, locale, f"Article {locale}", "Lampadaires")

                tags = entry.get_latest_revision_as_object().tags.all()
                self.assertEqual([tag.name for tag in tags], ["Lampadaires"])

    def test_editor_creates_a_tag_from_a_blog_entry(self):
        self.create_blog_entry(self.users["editeur-a"], self.site_a, "fr", "Article", "Réverbères")

        self.assertTrue(Tag.objects.filter(name="Réverbères").exists())


class MonositeSharedSnippetsTestCase(SharedSnippetsTestsMixin, MonositeTestCase):
    def test_editor_with_permissions_manages_the_shared_snippets(self):
        editor = self.users["editeur-a"]
        self.client.force_login(editor)

        for name, url in self.get_snippet_urls().items():
            with self.subTest(name):
                self.assertEqual(self.client.get(url).status_code, 200)

        self.assertTrue({"snippets", "proconnect"} <= self.get_menu_item_names(editor))
        self.assertIn("tag", self.get_snippet_model_names(editor))


class MultisiteSharedSnippetsTestCase(SharedSnippetsTestsMixin, MultisiteTestCase):
    def test_editor_with_permissions_does_not_access_the_shared_snippets(self):
        editor = self.users["editeur-a"]
        self.client.force_login(editor)

        for name, url in self.get_snippet_urls().items():
            with self.subTest(name):
                self.assertAccessDenied(url)

        self.assertNotIn("proconnect", self.get_menu_item_names(editor))
        self.assertNotIn("tag", self.get_snippet_model_names(editor))

    def test_editor_gets_a_403_on_the_tag_chooser_in_a_modal(self):
        self.client.force_login(self.users["editeur-a"])

        response = self.client.get(
            reverse("wagtailsnippetchoosers_sites_conformes_core_tag:choose"),
            headers={"x-requested-with": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 403)

    def test_site_administrator_does_not_access_the_shared_snippets(self):
        self.client.force_login(self.users["admin-a"])

        for name, url in self.get_snippet_urls().items():
            with self.subTest(name):
                self.assertAccessDenied(url)

    def test_editor_gets_tag_suggestions_of_every_site(self):
        self.create_blog_entry(self.users["editeur-b"], self.site_b, "fr", "Article B", "Étoiles")
        self.client.force_login(self.users["editeur-a"])

        response = self.client.get(reverse("wagtailadmin_tag_autocomplete"), {"term": "É"})

        self.assertEqual(response.json(), ["Étoiles"])
