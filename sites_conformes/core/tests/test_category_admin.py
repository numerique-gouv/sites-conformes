from importlib import import_module

from bs4 import BeautifulSoup
from django.apps import apps
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.translation import gettext
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.models import Category

User = get_user_model()


class CategoryTreeTest(WagtailPageTestCase):
    def setUp(self):
        self.theme = Category.objects.create(name="Thème", slug="theme")
        self.housing = Category.objects.create(name="Logement", slug="logement", parent=self.theme)
        self.jobs = Category.objects.create(name="Emploi", slug="emploi", parent=self.theme)
        self.public = Category.objects.create(name="Public", slug="public")
        self.companies = Category.objects.create(name="Entreprises", slug="entreprises", parent=self.public)

    def test_tree_lists_children_after_their_parent_sorted_by_name(self):
        self.assertEqual(
            [category.name for category in Category.get_tree()],
            ["Public", "Entreprises", "Thème", "Emploi", "Logement"],
        )

    def test_depth(self):
        depths = {category.name: category.get_depth() for category in Category.get_tree()}

        self.assertEqual(depths["Thème"], 1)
        self.assertEqual(depths["Logement"], 2)

    def test_deleting_a_parent_deletes_its_subtree(self):
        self.theme.delete()

        self.assertEqual(set(Category.objects.values_list("name", flat=True)), {"Public", "Entreprises"})

    def test_migration_breaks_parent_cycles_left_by_the_old_validation(self):
        Category.objects.filter(pk=self.theme.pk).update(parent=self.housing)  # Thème -> Logement -> Thème
        break_cycles = import_module("sites_conformes.core.migrations.0087_category_parent_cascade").break_cycles

        break_cycles(apps, None)

        roots = set(Category.objects.filter(parent=None).values_list("name", flat=True))
        self.assertIn("Public", roots)
        self.assertTrue({"Thème", "Logement"} & roots, "one node of the cycle is back at the root")
        self.assertEqual([c.name for c in Category.get_tree()][:1] and len(Category.get_tree()), 5)


class CategoryAdminTest(WagtailPageTestCase):
    form_data = {"colophon-count": "0", "treebeard_position": "sorted-child"}

    def setUp(self):
        self.login()
        self.theme = Category.objects.create(name="Thème", slug="theme")
        self.housing = Category.objects.create(name="Logement", slug="logement", parent=self.theme)
        self.public = Category.objects.create(name="Public", slug="public")

    def test_listing_nests_children_inside_their_parent(self):
        response = self.client.get(reverse("wagtailsnippets_sites_conformes_core_category:list"))

        self.assertEqual(response.status_code, 200)
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertIsNotNone(soup.select_one(f'[data-node="{self.theme.pk}"] [data-node="{self.housing.pk}"]'))
        self.assertIsNotNone(soup.select_one("[data-root-zone]"))

    def test_search_falls_back_to_the_flat_table(self):
        response = self.client.get(reverse("wagtailsnippets_sites_conformes_core_category:list") + "?q=Logement")

        self.assertContains(response, "Logement")
        self.assertNotContains(response, 'data-controller="sf-category-tree"')

    def test_drop_on_a_category_nests_under_it(self):
        response = self.client.post(
            reverse("wagtailsnippets_sites_conformes_core_category:move"),
            {"node": self.housing.pk, "target": self.public.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.housing.refresh_from_db()
        self.assertEqual(self.housing.parent, self.public)

    def test_drop_on_the_root_zone_makes_a_root(self):
        response = self.client.post(
            reverse("wagtailsnippets_sites_conformes_core_category:move"), {"node": self.housing.pk}
        )

        self.assertEqual(response.status_code, 200)
        self.housing.refresh_from_db()
        self.assertIsNone(self.housing.parent)

    def test_drop_on_a_descendant_is_refused(self):
        response = self.client.post(
            reverse("wagtailsnippets_sites_conformes_core_category:move"),
            {"node": self.theme.pk, "target": self.housing.pk},
        )

        self.assertEqual(response.status_code, 400)
        self.theme.refresh_from_db()
        self.assertIsNone(self.theme.parent)

    def test_create_view_places_the_category_under_the_chosen_parent(self):
        response = self.client.post(
            reverse("wagtailsnippets_sites_conformes_core_category:add"),
            {**self.form_data, "name": "Emploi", "slug": "emploi", "treebeard_ref_node": self.theme.pk},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Category.objects.get(slug="emploi").parent, self.theme)

    def test_edit_view_moves_the_category_under_another_parent(self):
        response = self.client.post(
            reverse("wagtailsnippets_sites_conformes_core_category:edit", args=[self.housing.pk]),
            {**self.form_data, "name": "Logement", "slug": "logement", "treebeard_ref_node": self.public.pk},
        )

        self.assertEqual(response.status_code, 302)
        self.housing.refresh_from_db()
        self.assertEqual(self.housing.parent, self.public)

    def test_a_category_cannot_be_moved_under_its_own_child(self):
        response = self.client.post(
            reverse("wagtailsnippets_sites_conformes_core_category:edit", args=[self.theme.pk]),
            {**self.form_data, "name": "Thème", "slug": "theme", "treebeard_ref_node": self.housing.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, gettext("A category cannot be moved under itself or one of its sub-categories."))
        self.theme.refresh_from_db()
        self.assertIsNone(self.theme.parent)
