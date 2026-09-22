from django.contrib.auth import get_user_model
from django.urls import reverse
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.models import Category

User = get_user_model()


class CategoryTreeOrderTest(WagtailPageTestCase):
    def setUp(self):
        self.theme = Category.objects.create(name="Thème", slug="theme")
        self.housing = Category.objects.create(name="Logement", slug="logement", parent=self.theme)
        self.jobs = Category.objects.create(name="Emploi", slug="emploi", parent=self.theme)
        self.public = Category.objects.create(name="Public", slug="public")
        self.companies = Category.objects.create(name="Entreprises", slug="entreprises", parent=self.public)

    def test_children_follow_their_parent(self):
        ordered = Category.in_tree_order()

        self.assertEqual(
            [category.name for category in ordered],
            ["Public", "Entreprises", "Thème", "Emploi", "Logement"],
        )

    def test_depth_is_annotated(self):
        depths = {category.name: category.tree_depth for category in Category.in_tree_order()}

        self.assertEqual(depths["Thème"], 0)
        self.assertEqual(depths["Logement"], 1)

    def test_a_category_whose_parent_is_filtered_out_is_still_listed(self):
        ordered = Category.in_tree_order(Category.objects.filter(parent=self.theme))

        self.assertEqual({category.name for category in ordered}, {"Logement", "Emploi"})

    def test_a_cycle_in_the_data_does_not_hang_the_listing(self):
        """``clean`` forbids cycles in forms, but nothing stops them at the database level."""
        Category.objects.filter(pk=self.theme.pk).update(parent=self.housing)

        ordered = Category.in_tree_order()

        self.assertEqual(len(ordered), Category.objects.count())
        self.assertEqual(len({category.pk for category in ordered}), Category.objects.count())

    def test_is_child_marks_only_children(self):
        self.assertFalse(self.theme.is_child)
        self.assertTrue(self.housing.is_child)


class CategoryAdminListingTest(WagtailPageTestCase):
    def setUp(self):
        self.login()
        self.theme = Category.objects.create(name="Thème", slug="theme")
        self.housing = Category.objects.create(name="Logement", slug="logement", parent=self.theme)

    def test_listing_shows_children_after_their_parent(self):
        response = self.client.get(reverse("wagtailsnippets_sites_conformes_core_category:list"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertLess(content.index("Thème"), content.index("Logement"))
