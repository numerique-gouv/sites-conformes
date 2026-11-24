from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from sites_conformes.core.services.demo_sites import get_permission
from sites_conformes.core.tests.base import MonositeTestCase, MultisiteTestCase
from sites_conformes.dashboard.views import get_shortcuts_site


def home_page_edit_url(site) -> str:
    return reverse("wagtailadmin_pages:edit", args=[site.root_page.pk])


class MonositeShortcutsTestCase(MonositeTestCase):
    def test_shortcuts_target_the_default_site(self):
        self.assertEqual(get_shortcuts_site(self.users["moderateur-a"]), self.site_a)


class MultisiteShortcutsTestCase(MultisiteTestCase):
    def test_shortcuts_of_the_moderator_of_site_b_target_site_b(self):
        self.assertEqual(get_shortcuts_site(self.users["moderateur-b"]), self.site_b)

        self.client.force_login(self.users["moderateur-b"])
        response = self.client.get(reverse("wagtailadmin_home"))
        self.assertContains(response, home_page_edit_url(self.site_b))
        self.assertContains(response, reverse("wagtailadmin_explore", args=[self.site_b.root_page.pk]))
        self.assertNotContains(response, home_page_edit_url(self.site_a))

    def test_shortcuts_target_the_default_site_when_it_is_in_the_scope(self):
        # Site A is the default site
        self.assertEqual(get_shortcuts_site(self.users["editeur-ab"]), self.site_a)
        self.assertEqual(get_shortcuts_site(self.users["superadmin"]), self.site_a)

    def test_no_shortcuts_without_site(self):
        group = Group.objects.create(name="Accès à l’administration")
        group.permissions.add(get_permission("wagtailadmin.access_admin"))
        user = get_user_model().objects.create(username="sans-site")
        user.groups.add(group)
        self.assertIsNone(get_shortcuts_site(user))

        self.client.force_login(user)
        response = self.client.get(reverse("wagtailadmin_home"))
        self.assertEqual(response.status_code, 200)
