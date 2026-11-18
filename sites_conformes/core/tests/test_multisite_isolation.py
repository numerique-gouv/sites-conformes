from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.core import checks
from django.test import override_settings
from wagtail.contrib.redirects.models import Redirect
from wagtail.models import GroupPagePermission, Page, Site

from sites_conformes.core.multisite_isolation import (
    check_multisite_isolation_setting,
    get_objects_for_page_form,
    get_site_for_page,
    get_sites_for_user,
    is_multisite_isolation_active,
)
from sites_conformes.core.tests.base import MonositeTestCase, MultisiteTestCase


class MultisiteIsolationTestsMixin:
    """
    Tests run in both configurations.
    """

    def get_page(self, site: Site, path: str) -> Page:
        page = site.root_page
        for slug in path.strip("/").split("/"):
            page = page.get_children().get(slug=slug)
        return page

    def create_user_with_page_permission(self, page: Page):
        group = Group.objects.create(name=f"Droit sur {page.title}")
        GroupPagePermission.objects.create(
            group=group,
            page=page,
            permission=Permission.objects.get(content_type__app_label="wagtailcore", codename="change_page"),
        )
        user = get_user_model().objects.create(username=f"droit-{page.pk}")
        user.groups.add(group)
        return user

    def get_fresh_user(self, username: str):
        # Without the sites cached on the object
        return get_user_model().objects.get(username=username)

    def assertSites(self, user, expected: list):
        self.assertEqual({site.hostname for site in get_sites_for_user(user)}, {site.hostname for site in expected})

    # get_sites_for_user

    def test_editor_has_access_to_site_a(self):
        self.assertSites(self.users["editeur-a"], [self.site_a])

    def test_superadmin_has_access_to_every_site(self):
        self.assertSites(self.users["superadmin"], list(Site.objects.all()))

    def test_account_without_group_has_access_to_no_site(self):
        user = get_user_model().objects.create(username="sans-groupe")
        self.assertEqual(get_sites_for_user(user), [])

    def test_inactive_accounts_have_access_to_no_site(self):
        for username in ["editeur-a", "superadmin"]:
            with self.subTest(username=username):
                user = self.get_fresh_user(username)
                user.is_active = False
                self.assertEqual(get_sites_for_user(user), [])

    def test_anonymous_user_has_access_to_no_site(self):
        self.assertEqual(get_sites_for_user(AnonymousUser()), [])

    def test_permission_on_the_root_of_the_tree_gives_access_to_every_site(self):
        user = self.create_user_with_page_permission(Page.get_first_root_node())
        self.assertSites(user, list(Site.objects.all()))

    def test_permission_on_a_page_outside_of_every_site_gives_access_to_no_site(self):
        orphan = Page.get_first_root_node().add_child(instance=Page(title="Orpheline", slug="orpheline"))
        user = self.create_user_with_page_permission(orphan)
        self.assertEqual(get_sites_for_user(user), [])

    def test_sites_are_cached_on_the_user(self):
        user = self.get_fresh_user("editeur-a")
        self.assertSites(user, [self.site_a])

        user.groups.clear()
        with self.assertNumQueries(0):
            self.assertSites(user, [self.site_a])
        # A new object of the same user computes them again
        self.assertEqual(get_sites_for_user(self.get_fresh_user("editeur-a")), [])

    def test_cached_sites_cannot_be_modified_by_the_caller(self):
        user = self.get_fresh_user("editeur-a")
        get_sites_for_user(user).clear()
        self.assertSites(user, [self.site_a])

    # get_site_for_page

    def test_site_of_a_page_of_site_a(self):
        page = self.get_page(self.site_a, "le-ministere/nos-missions")
        self.assertEqual(get_site_for_page(page), self.site_a)

    def test_site_of_a_page_of_the_english_tree_of_site_a(self):
        page_en = self.get_page(self.site_a, "le-ministere/nos-missions").get_translations().get()
        self.assertFalse(page_en.is_descendant_of(self.site_a.root_page))
        self.assertEqual(get_site_for_page(page_en), self.site_a)

    def test_site_of_a_page_being_created_under_a_page_of_site_a(self):
        parent = self.get_page(self.site_a, "le-ministere")
        self.assertEqual(get_site_for_page(Page(title="Nouvelle page"), parent_page=parent), self.site_a)
        self.assertEqual(get_site_for_page(None, parent_page=parent), self.site_a)

    def test_site_of_a_page_outside_of_every_site(self):
        orphan = Page.get_first_root_node().add_child(instance=Page(title="Orpheline", slug="orpheline"))
        self.assertIsNone(get_site_for_page(orphan))
        self.assertIsNone(get_site_for_page(Page(title="Nouvelle page"), parent_page=orphan))
        self.assertIsNone(get_site_for_page(Page(title="Nouvelle page")))

    # get_objects_for_page_form

    def test_objects_without_site(self):
        without_site = Redirect.objects.create(old_path="/sans-site", site=None)
        of_site_a = Redirect.objects.create(old_path="/site-a", site=self.site_a)

        self.assertQuerySetEqual(get_objects_for_page_form(Redirect.objects.all(), None, []), [without_site])
        self.assertQuerySetEqual(
            get_objects_for_page_form(Redirect.objects.all(), None, [of_site_a.pk]),
            [without_site, of_site_a],
            ordered=False,
        )

    def test_objects_are_taken_from_the_given_queryset(self):
        Redirect.objects.create(old_path="/site-a-1", site=self.site_a)
        kept = Redirect.objects.create(old_path="/site-a-2", site=self.site_a)
        queryset = Redirect.objects.filter(old_path="/site-a-2")
        self.assertQuerySetEqual(get_objects_for_page_form(queryset, self.site_a, None), [kept])

    # is_multisite_isolation_active

    @override_settings()
    def test_isolation_is_inactive_without_the_setting(self):
        del settings.SF_MULTISITE_ISOLATION_ENABLED
        self.assertFalse(is_multisite_isolation_active())

    @override_settings(SF_MULTISITE_ISOLATION_ENABLED=True)
    def test_isolation_is_active_with_the_setting(self):
        self.assertTrue(is_multisite_isolation_active())

    # System check

    def get_isolation_warnings(self):
        return [
            message
            for message in checks.run_checks(tags=[checks.Tags.database], databases=["default"])
            if message.id == "sites_conformes_core.W001"
        ]

    @override_settings(SF_MULTISITE_ISOLATION_ENABLED=True)
    def test_no_warning_when_the_isolation_is_enabled(self):
        self.assertEqual(self.get_isolation_warnings(), [])

    @override_settings(SF_MULTISITE_ISOLATION_ENABLED=False)
    def test_no_warning_without_database(self):
        # The check counts the sites, so it only runs with the commands that use the database
        self.assertEqual(check_multisite_isolation_setting(databases=None), [])


class MonositeIsolationTestCase(MultisiteIsolationTestsMixin, MonositeTestCase):
    def test_isolation_is_inactive(self):
        self.assertFalse(is_multisite_isolation_active())

    def test_no_warning_with_a_single_site(self):
        self.assertEqual(Site.objects.count(), 1)
        self.assertEqual(self.get_isolation_warnings(), [])


class MultisiteIsolationTestCase(MultisiteIsolationTestsMixin, MultisiteTestCase):
    def test_isolation_is_active(self):
        self.assertTrue(is_multisite_isolation_active())

    def test_superadmin_has_access_to_sites_a_and_b(self):
        self.assertSites(self.users["superadmin"], [self.site_a, self.site_b])

    def test_editors_have_access_to_their_sites(self):
        self.assertSites(self.users["editeur-b"], [self.site_b])
        self.assertSites(self.users["editeur-ab"], [self.site_a, self.site_b])

    def test_permission_on_the_root_of_the_tree_gives_access_to_sites_a_and_b(self):
        user = self.create_user_with_page_permission(Page.get_first_root_node())
        self.assertSites(user, [self.site_a, self.site_b])

    def test_permission_on_a_subpage_of_site_b(self):
        user = self.create_user_with_page_permission(self.get_page(self.site_b, "demarches/par-planete"))
        self.assertSites(user, [self.site_b])

    def test_permission_only_on_the_english_root_of_site_b(self):
        home_en = self.site_b.root_page.get_translations().get()
        user = self.create_user_with_page_permission(home_en)
        self.assertSites(user, [self.site_b])

    def test_permission_on_an_english_subpage_of_site_a(self):
        page_en = self.get_page(self.site_a, "le-ministere/nos-missions").get_translations().get()
        user = self.create_user_with_page_permission(page_en)
        self.assertSites(user, [self.site_a])

    def test_site_of_a_page_being_created_under_a_page_of_site_b(self):
        parent = self.get_page(self.site_b, "demarches/par-planete")
        self.assertEqual(get_site_for_page(Page(title="Nouvelle fiche"), parent_page=parent), self.site_b)

    def test_saved_page_ignores_the_parent_page(self):
        page = self.get_page(self.site_a, "contact")
        parent_b = self.get_page(self.site_b, "contact")
        self.assertEqual(get_site_for_page(page, parent_page=parent_b), self.site_a)

    def test_objects_of_site_a_and_a_value_already_selected_outside_of_site_a(self):
        of_site_a = Redirect.objects.create(old_path="/site-a", site=self.site_a)
        of_site_b = Redirect.objects.create(old_path="/site-b", site=self.site_b)
        other_of_site_b = Redirect.objects.create(old_path="/autre-site-b", site=self.site_b)
        without_site = Redirect.objects.create(old_path="/sans-site", site=None)

        # Without current value: only the objects of site A
        self.assertQuerySetEqual(get_objects_for_page_form(Redirect.objects.all(), self.site_a, []), [of_site_a])

        # The current value is kept, given as an object or as a primary key
        for current_values in [[of_site_b], [of_site_b.pk], Redirect.objects.filter(pk=of_site_b.pk)]:
            with self.subTest(current_values=current_values):
                objects = get_objects_for_page_form(Redirect.objects.all(), self.site_a, current_values)
                self.assertQuerySetEqual(objects, [of_site_a, of_site_b], ordered=False)
                self.assertNotIn(other_of_site_b, objects)
                self.assertNotIn(without_site, objects)

    @override_settings(SF_MULTISITE_ISOLATION_ENABLED=False)
    def test_warning_with_several_sites_and_the_isolation_disabled(self):
        self.assertFalse(is_multisite_isolation_active())
        warnings = self.get_isolation_warnings()
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].level, checks.WARNING)
        self.assertIn("SF_MULTISITE_ISOLATION_ENABLED", warnings[0].hint)
