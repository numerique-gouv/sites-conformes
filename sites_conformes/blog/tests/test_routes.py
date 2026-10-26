import zoneinfo
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils.translation import gettext
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.blog.models import BlogEntryPage, BlogIndexPage, Category
from sites_conformes.blog.tests.factories import CategoryFactory
from sites_conformes.core.models import Tag

User = get_user_model()


class BlogIndexRoutesTestCase(WagtailPageTestCase):
    def setUp(self):
        home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.blog_index_page = home.add_child(instance=BlogIndexPage(title="Actualités", slug="actualites"))

        self.blog_post = self.blog_index_page.add_child(
            instance=BlogEntryPage(
                title="J’accuse",
                date=datetime(1898, 1, 13, 6, 0, 0, tzinfo=zoneinfo.ZoneInfo("Europe/Paris")),
                owner=self.admin,
            )
        )
        self.category = CategoryFactory(name="Presse")
        self.blog_post.blog_categories.add(self.category)
        self.blog_post.tags.add(Tag.objects.create(name="Écrits", slug="ecrits"))
        self.blog_post.save_revision().publish()

    def test_atom_feed(self):
        response = self.client.get(self.blog_index_page.url + "atom/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/xml")
        self.assertContains(response, 'xmlns="http://www.w3.org/2005/Atom"')
        self.assertContains(response, "J’accuse")

    def test_atom_feed_uses_seo_title(self):
        self.blog_index_page.seo_title = "Le journal"
        self.blog_index_page.save()

        response = self.client.get(self.blog_index_page.url + "atom/")

        self.assertContains(response, "<title>Le journal</title>")

    def test_categories_list(self):
        response = self.client.get(self.blog_index_page.url + "categories/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Presse")

    def test_tags_list(self):
        response = self.client.get(self.blog_index_page.url + "tags/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Écrits")
        # Tags are grouped by their first letter, without accents
        self.assertIn("E", response.context["sorted_tags"])


class CategoryTestCase(TestCase):
    def test_slug_is_generated(self):
        category = CategoryFactory(name="Vie pratique", slug="")

        self.assertEqual(category.slug, "vie-pratique")

    def test_category_cannot_be_its_own_parent(self):
        category = CategoryFactory()
        category.parent = category

        with self.assertRaisesMessage(ValidationError, gettext("Parent category cannot be self.")):
            category.clean()

    def test_categories_cannot_be_circular(self):
        parent = CategoryFactory()
        child = CategoryFactory(parent=parent)
        parent.parent = child

        with self.assertRaisesMessage(ValidationError, gettext("Cannot have circular Parents.")):
            parent.clean()

    def test_valid_parent(self):
        parent = CategoryFactory()
        child = Category(name="Enfant", parent=parent)

        child.clean()
