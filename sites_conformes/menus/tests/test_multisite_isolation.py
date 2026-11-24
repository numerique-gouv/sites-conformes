from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Group
from django.core import checks
from django.test import override_settings
from django.urls import reverse

from sites_conformes.core.multisite_isolation import check_groups_without_site
from sites_conformes.core.services.demo_sites import EDITORS, MODERATORS, get_permission, get_site_group
from sites_conformes.core.tests.base import MonositeTestCase, MultisiteTestCase
from sites_conformes.menus.models import FooterBottomMenu, MainMenu, TopMenu

MENU_MODELS = [TopMenu, MainMenu, FooterBottomMenu]


def snippet_url(model, view: str, *args) -> str:
    return reverse(f"wagtailsnippets_sites_conformes_menus_{model._meta.model_name}:{view}", args=args)


def chooser_url(model, view: str, *args) -> str:
    return reverse(f"wagtailsnippetchoosers_sites_conformes_menus_{model._meta.model_name}:{view}", args=args)


class MenusTestsMixin:
    def login(self, username: str):
        self.client.force_login(self.users[username])

    def get_add_form(self, model=MainMenu, query: str = ""):
        response = self.client.get(snippet_url(model, "add") + query)
        self.assertEqual(response.status_code, 200)
        return response.context["form"]

    def get_site_choices(self, form) -> set:
        return set(form.fields["site"].queryset)

    def test_editor_has_no_access_to_menus(self):
        self.login("editeur-a")
        for model in MENU_MODELS:
            with self.subTest(model=model.__name__):
                response = self.client.get(snippet_url(model, "list"))
                self.assertRedirects(response, reverse("wagtailadmin_home"))

    def test_moderator_manages_the_menus_of_site_a(self):
        self.login("moderateur-a")
        menu = MainMenu.objects.filter(site=self.site_a).first()
        for view in ["edit", "delete", "copy", "history", "usage"]:
            with self.subTest(view=view):
                self.assertEqual(self.client.get(snippet_url(MainMenu, view, menu.pk)).status_code, 200)

    def test_wagtailmenus_is_not_editable_in_the_admin(self):
        self.client.force_login(self.users["superadmin"])
        for model_name in ["mainmenu", "flatmenu"]:
            with self.subTest(model=model_name):
                response = self.client.get(f"/{settings.WAGTAILADMIN_PATH}snippets/wagtailmenus/{model_name}/")
                self.assertEqual(response.status_code, 404)

    def test_mega_menus_no_longer_exist(self):
        for model_name in ["MegaMenu", "MegaMenuCategory"]:
            with self.subTest(model=model_name), self.assertRaises(LookupError):
                apps.get_model("sites_conformes_core", model_name)


class MonositeMenusTestCase(MenusTestsMixin, MonositeTestCase):
    def test_site_field_is_unchanged(self):
        self.login("moderateur-a")
        form = self.get_add_form()
        self.assertEqual(form.fields["site"].queryset.model.objects.count(), form.fields["site"].queryset.count())
        self.assertEqual(form.initial["site"], MainMenu._meta.get_field("site").get_default())

    @override_settings(SF_MULTISITE_ISOLATION_ENABLED=True)
    def test_same_access_with_the_isolation_enabled(self):
        self.login("moderateur-a")
        form = self.get_add_form()
        self.assertEqual(self.get_site_choices(form), {self.site_a})
        self.assertEqual(form.initial["site"], self.site_a.pk)

        response = self.client.get(snippet_url(MainMenu, "list"))
        for menu in MainMenu.objects.all():
            self.assertContains(response, snippet_url(MainMenu, "edit", menu.pk))

    def test_no_message_about_groups_with_a_single_site(self):
        Group.objects.create(name="Menus seulement").permissions.add(
            get_permission("sites_conformes_menus.change_mainmenu")
        )
        self.assertEqual(check_groups_without_site(databases=["default"]), [])


class MultisiteMenusTestCase(MenusTestsMixin, MultisiteTestCase):
    def test_moderator_only_lists_the_menus_of_site_a(self):
        self.login("moderateur-a")
        for model in MENU_MODELS:
            with self.subTest(model=model.__name__):
                response = self.client.get(snippet_url(model, "list"))
                self.assertEqual(response.status_code, 200)
                for menu in model.objects.filter(site=self.site_a):
                    self.assertContains(response, snippet_url(model, "edit", menu.pk))
                for menu in model.objects.filter(site=self.site_b):
                    self.assertNotContains(response, snippet_url(model, "edit", menu.pk))
                self.assertNotContains(response, self.site_b.hostname)

    def test_site_field_only_offers_site_a(self):
        self.login("moderateur-a")
        for model in MENU_MODELS:
            with self.subTest(model=model.__name__):
                form = self.get_add_form(model)
                self.assertEqual(self.get_site_choices(form), {self.site_a})
                self.assertEqual(form.initial["site"], self.site_a.pk)

    def test_site_is_not_preselected_with_several_sites(self):
        # Site A is the default site: its primary key is the default value of the field
        user = self.users["moderateur-a"]
        user.groups.add(get_site_group("b", MODERATORS))
        self.login("moderateur-a")
        form = self.get_add_form(TopMenu)
        self.assertEqual(self.get_site_choices(form), {self.site_a, self.site_b})
        self.assertIsNone(form.initial["site"])

    def test_superadmin_manages_every_menu(self):
        self.login("superadmin")
        response = self.client.get(snippet_url(MainMenu, "list"))
        for menu in MainMenu.objects.all():
            self.assertContains(response, snippet_url(MainMenu, "edit", menu.pk))
        form = self.get_add_form()
        self.assertEqual(self.get_site_choices(form), {self.site_a, self.site_b})

    def test_views_of_a_menu_of_site_b_return_a_404(self):
        self.login("moderateur-a")
        for model in [MainMenu, FooterBottomMenu]:
            menu = model.objects.filter(site=self.site_b).first()
            for view in ["edit", "delete", "copy", "history", "history_results", "usage"]:
                with self.subTest(model=model.__name__, view=view):
                    self.assertEqual(self.client.get(snippet_url(model, view, menu.pk)).status_code, 404)
            with self.subTest(model=model.__name__, view="delete (POST)"):
                self.assertEqual(self.client.post(snippet_url(model, "delete", menu.pk)).status_code, 404)
                self.assertTrue(model.objects.filter(pk=menu.pk).exists())

    def test_moderator_of_site_b_has_no_access_to_the_menus_of_site_a(self):
        self.login("moderateur-b")
        menu = MainMenu.objects.filter(site=self.site_a).first()
        self.assertEqual(self.client.get(snippet_url(MainMenu, "edit", menu.pk)).status_code, 404)

    def test_scope_follows_the_permission_on_menus(self):
        # Editor of site B: page permissions on B, but no permission on menus there
        user = self.users["moderateur-a"]
        user.groups.add(get_site_group("b", EDITORS))
        self.login("moderateur-a")
        menu_b = MainMenu.objects.filter(site=self.site_b).first()
        self.assertEqual(self.client.get(snippet_url(MainMenu, "edit", menu_b.pk)).status_code, 404)
        self.assertEqual(self.get_site_choices(self.get_add_form()), {self.site_a})

    def test_menu_cannot_be_moved_to_site_b(self):
        self.login("moderateur-a")
        menu = TopMenu.objects.create(site=self.site_a)
        response = self.client.post(snippet_url(TopMenu, "edit", menu.pk), {"site": self.site_b.pk, "items-count": 0})
        self.assertEqual(response.status_code, 200)
        self.assertIn("site", response.context["form"].errors)
        menu.refresh_from_db()
        self.assertEqual(menu.site, self.site_a)

    def test_menu_cannot_be_created_on_site_b(self):
        self.login("moderateur-a")
        response = self.client.post(snippet_url(TopMenu, "add"), {"site": self.site_b.pk, "items-count": 0})
        self.assertEqual(response.status_code, 200)
        self.assertIn("site", response.context["form"].errors)
        self.assertFalse(TopMenu.objects.exists())

    def test_english_menu_of_site_a_is_only_shown_on_site_a(self):
        self.login("moderateur-a")
        response = self.client.post(
            snippet_url(TopMenu, "add") + "?locale=en", {"site": self.site_a.pk, "items-count": 0}
        )
        self.assertEqual(response.status_code, 302)
        menu = TopMenu.objects.get()
        self.assertEqual((menu.site, menu.locale.language_code), (self.site_a, "en"))

        menu.items = [
            ("link", {"link_type": "external_url", "external_url": "https://example.org/", "text": "Lien A"})
        ]
        menu.save()
        self.assertContains(self.client.get("/en/", HTTP_HOST=self.site_a.hostname), "Lien A")
        self.assertNotContains(self.client.get("/en/", HTTP_HOST=self.site_b.hostname), "Lien A")

    def test_chooser_only_offers_the_menus_of_site_a(self):
        self.login("moderateur-a")
        response = self.client.get(chooser_url(MainMenu, "choose"))
        self.assertEqual(response.status_code, 200)
        html = response.json()["html"]
        for menu in MainMenu.objects.all():
            with self.subTest(menu=str(menu)):
                self.assertEqual(chooser_url(MainMenu, "chosen", menu.pk) in html, menu.site == self.site_a)

        menu_b = MainMenu.objects.filter(site=self.site_b).first()
        self.assertEqual(self.client.get(chooser_url(MainMenu, "chosen", menu_b.pk)).status_code, 404)
        response = self.client.get(chooser_url(MainMenu, "chosen_multiple"), {"id": [menu_b.pk]})
        self.assertEqual(response.json()["result"], [])

    def bulk_delete_url(self, model, ids) -> str:
        url = reverse("wagtail_bulk_action", args=["sites_conformes_menus", model._meta.model_name, "delete"])
        return url + "?" + "&".join(f"id={pk}" for pk in ids)

    def test_bulk_delete_of_a_menu_of_site_b_returns_a_404(self):
        self.login("moderateur-a")
        menu_a = MainMenu.objects.filter(site=self.site_a).first()
        menu_b = MainMenu.objects.filter(site=self.site_b).first()
        for ids in [[menu_b.pk], [menu_a.pk, menu_b.pk]]:
            with self.subTest(ids=ids):
                self.assertEqual(self.client.get(self.bulk_delete_url(MainMenu, ids)).status_code, 404)
                self.assertEqual(self.client.post(self.bulk_delete_url(MainMenu, ids)).status_code, 404)
        self.assertTrue(MainMenu.objects.filter(pk=menu_b.pk).exists())

        self.assertEqual(self.client.get(self.bulk_delete_url(MainMenu, [menu_a.pk])).status_code, 200)

    def test_bulk_delete_of_all_menus_only_deletes_those_of_site_a(self):
        self.login("moderateur-a")
        self.client.post(self.bulk_delete_url(MainMenu, ["all"]))
        self.assertFalse(MainMenu.objects.filter(site=self.site_a).exists())
        self.assertEqual(MainMenu.objects.filter(site=self.site_b).count(), 2)

    def test_translation_of_a_menu_of_site_b_returns_a_404(self):
        self.login("moderateur-a")
        menu_b = MainMenu.objects.filter(site=self.site_b, locale__language_code="fr").first()
        for name in ["wagtail_localize:submit_snippet_translation", "wagtail_localize:snippets_api_detail"]:
            with self.subTest(view=name):
                url = reverse(name, args=["sites_conformes_menus", "mainmenu", menu_b.pk])
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_groups_without_page_permission_are_listed(self):
        group = Group.objects.create(name="Menus seulement")
        group.permissions.add(get_permission("sites_conformes_menus.change_mainmenu"))
        Group.objects.create(name="Sans droit sur les menus").permissions.add(
            get_permission("sites_conformes_blog.change_category")
        )

        messages = check_groups_without_site(databases=["default"])
        self.assertEqual([message.id for message in messages], ["sites_conformes_core.W001"])
        self.assertIsInstance(messages[0], checks.Warning)
        self.assertIn('"Menus seulement"', messages[0].msg)
        self.assertNotIn("Sans droit sur les menus", messages[0].msg)
        self.assertNotIn(MODERATORS, messages[0].msg)

    def test_no_message_when_every_group_has_page_permissions(self):
        self.assertEqual(check_groups_without_site(databases=["default"]), [])

    def test_no_message_without_database(self):
        Group.objects.create(name="Menus seulement").permissions.add(
            get_permission("sites_conformes_menus.change_mainmenu")
        )
        self.assertEqual(check_groups_without_site(databases=None), [])
