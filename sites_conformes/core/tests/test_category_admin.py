from importlib import import_module

from bs4 import BeautifulSoup
from django.apps import apps
from django.contrib.auth import get_user_model
from django.urls import reverse
from wagtail.test.utils import WagtailPageTestCase
from wagtail_in_a_tree.forms import INVALID_MOVE_MESSAGE

from sites_conformes.core.models import Category

User = get_user_model()


class CategoryTreeTest(WagtailPageTestCase):
    def setUp(self):
        self.theme = Category.objects.create(name="Thème", slug="theme")
        self.housing = Category.objects.create(name="Logement", slug="logement", parent=self.theme)
        self.jobs = Category.objects.create(name="Emploi", slug="emploi", parent=self.theme)
        self.public = Category.objects.create(name="Public", slug="public")
        self.companies = Category.objects.create(name="Entreprises", slug="entreprises", parent=self.public)

    def test_tree_lists_children_after_their_parent_in_creation_order(self):
        self.assertEqual(
            [category.name for category in Category.get_tree()],
            ["Thème", "Logement", "Emploi", "Public", "Entreprises"],
        )

    def test_migration_numbers_siblings_from_one_in_name_order(self):
        Category.objects.update(sib_order=0)
        number_siblings = import_module("sites_conformes.core.migrations.0088_category_sib_order").number_siblings

        number_siblings(apps, None)

        self.assertEqual([c.name for c in Category.get_root_nodes()], ["Public", "Thème"])
        self.assertEqual([c.name for c in self.theme.get_children()], ["Emploi", "Logement"])
        self.housing.refresh_from_db()
        self.housing.move(Category.objects.get(pk=self.jobs.pk), "left")
        self.assertEqual([c.name for c in self.theme.get_children()], ["Logement", "Emploi"])

    def test_siblings_can_be_reordered_by_hand(self):
        self.jobs.move(self.housing, "left")

        self.assertEqual([c.name for c in self.theme.get_children()], ["Emploi", "Logement"])

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
    form_data = {"colophon-count": "0", "treebeard_position": "first-child"}

    def setUp(self):
        self.login()
        self.theme = Category.objects.create(name="Thème", slug="theme")
        self.housing = Category.objects.create(name="Logement", slug="logement", parent=self.theme)
        self.public = Category.objects.create(name="Public", slug="public")

    def test_listing_shows_the_root_categories_only(self):
        response = self.client.get(reverse("wagtailsnippets_sites_conformes_core_category:list"))

        self.assertEqual(response.status_code, 200)
        soup = BeautifulSoup(response.content, "html.parser")
        rows = soup.select("tr[data-node]")
        self.assertEqual([row["data-node"] for row in rows], [str(self.theme.pk), str(self.public.pk)])

    def test_each_category_lists_its_children(self):
        response = self.client.get(
            reverse("wagtailsnippets_sites_conformes_core_category:children", args=[self.theme.pk])
        )

        soup = BeautifulSoup(response.content, "html.parser")
        self.assertEqual([row["data-node"] for row in soup.select("tr[data-node]")], [str(self.housing.pk)])

    def test_categories_have_their_own_menu_item(self):
        response = self.client.get(reverse("wagtailadmin_home"))

        self.assertContains(response, reverse("wagtailsnippets_sites_conformes_core_category:list"))

    def test_pages_choose_their_categories_in_a_tree(self):
        from wagtail_in_a_tree.widgets import TreeCheckboxSelectMultiple

        from sites_conformes.core.models import ContentPage

        form_class = ContentPage.get_edit_handler().get_form_class()

        self.assertIsInstance(form_class.base_fields["categories"].widget, TreeCheckboxSelectMultiple)

    def test_search_falls_back_to_the_flat_table(self):
        response = self.client.get(reverse("wagtailsnippets_sites_conformes_core_category:list") + "?q=Logement")

        self.assertContains(response, "Logement")
        self.assertNotContains(response, 'data-controller="tb-tree"')

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
        self.assertContains(response, INVALID_MOVE_MESSAGE)
        self.theme.refresh_from_db()
        self.assertIsNone(self.theme.parent)
