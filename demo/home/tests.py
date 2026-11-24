import swapper
from django.db import connection
from wagtail.models import Page, Site, get_page_models
from wagtail.test.utils import WagtailPageTestCase

from home.models import CustomBlogEntryPage, CustomContentPage, HomePage
from sites_conformes.blog import models as blog_models
from sites_conformes.blog.models import BlogEntryPage, BlogIndexPage
from sites_conformes.core import models as core_models
from sites_conformes.core.models import CatalogIndexPage, Category, ContentPage, Tag
from sites_conformes.core.services.accessors import get_or_create_content_page


class HomeSetUpTests(WagtailPageTestCase):
    """
    Tests for basic page structure setup and HomePage creation.
    """

    def test_root_create(self):
        root_page = Page.objects.get(pk=1)
        self.assertIsNotNone(root_page)

    def test_homepage_create(self):
        root_page = Page.objects.get(pk=1)
        homepage = HomePage(title="Home")
        root_page.add_child(instance=homepage)
        self.assertTrue(HomePage.objects.filter(title="Home").exists())


class HomeTests(WagtailPageTestCase):
    """
    Tests for homepage functionality and rendering.
    """

    def setUp(self):
        """
        Create a homepage instance for testing.
        """
        root_page = Page.get_first_root_node()
        Site.objects.create(hostname="testsite", root_page=root_page, is_default_site=True)
        self.homepage = HomePage(title="Home")
        root_page.add_child(instance=self.homepage)

    def test_homepage_is_renderable(self):
        self.assertPageIsRenderable(self.homepage)

    def test_homepage_template_used(self):
        response = self.client.get(self.homepage.url)
        self.assertTemplateUsed(response, "home/home_page.html")


class CustomContentPageTests(WagtailPageTestCase):
    """
    The shipped ContentPage is swapped for home.CustomContentPage (SF_CONTENTPAGE_MODEL).
    """

    @classmethod
    def setUpTestData(cls):
        cls.home = Site.objects.get(is_default_site=True).root_page

    def test_setting_swaps_the_model(self):
        self.assertIs(swapper.load_model("sites_conformes_core", "ContentPage"), CustomContentPage)
        self.assertEqual(ContentPage._meta.swapped, "home.CustomContentPage")

    def test_default_model_is_hidden_from_wagtail(self):
        self.assertNotIn(ContentPage, get_page_models())
        self.assertIn(CustomContentPage, get_page_models())
        self.assertCanCreateAt(CatalogIndexPage, CustomContentPage)
        self.assertCanNotCreateAt(CatalogIndexPage, ContentPage)

    def test_create_tag_and_render(self):
        page = self.home.add_child(instance=CustomContentPage(title="Custom", slug="custom", subtitle="sub"))
        page.tags.add("dsfr")
        page.save()

        self.assertEqual(list(CustomContentPage.objects.filter(tags__name="dsfr")), [page])
        self.assertPageIsRenderable(page)

    def test_shipped_tag_through_model_is_not_declared(self):
        self.assertFalse(hasattr(core_models, "TagContentPage"))
        self.assertFalse(hasattr(ContentPage, "tags"))
        tables = connection.introspection.table_names()
        self.assertNotIn("sites_conformes_core_contentpage", tables)
        self.assertNotIn("sites_conformes_core_tagcontentpage", tables)

    def test_tags_with_usecount_follows_the_swapped_through_model(self):
        page = self.home.add_child(instance=CustomContentPage(title="Tagged", slug="tagged", live=True))
        page.tags.add("dsfr")
        page.save()

        self.assertEqual([tag.name for tag in Tag.objects.tags_with_usecount(1)], ["dsfr"])

    def test_catalog_lists_custom_pages(self):
        catalog = self.home.add_child(instance=CatalogIndexPage(title="Catalogue", slug="catalogue"))
        child = catalog.add_child(instance=CustomContentPage(title="Entry", slug="entry", live=True))

        self.assertEqual(list(catalog.posts), [child])

    def test_accessor_creates_the_swapped_model(self):
        page = get_or_create_content_page(slug="via-accessor", title="Via accessor", body=[])
        self.assertIsInstance(page, CustomContentPage)


class CustomBlogEntryPageTests(WagtailPageTestCase):
    """
    The shipped BlogEntryPage is swapped for home.CustomBlogEntryPage (SF_BLOGENTRYPAGE_MODEL).
    """

    @classmethod
    def setUpTestData(cls):
        home = Site.objects.get(is_default_site=True).root_page
        cls.blog = home.add_child(instance=BlogIndexPage(title="Blog", slug="blog"))
        cls.category = Category.objects.create(name="Bretagne", slug="bretagne", locale=cls.blog.locale)

    def add_entry(self, slug, **kwargs):
        return self.blog.add_child(instance=CustomBlogEntryPage(title=slug.title(), slug=slug, live=True, **kwargs))

    def test_setting_swaps_the_model(self):
        self.assertIs(swapper.load_model("sites_conformes_blog", "BlogEntryPage"), CustomBlogEntryPage)
        self.assertEqual(BlogEntryPage._meta.swapped, "home.CustomBlogEntryPage")

    def test_default_model_is_hidden_from_wagtail(self):
        self.assertNotIn(BlogEntryPage, get_page_models())
        self.assertCanCreateAt(BlogIndexPage, CustomBlogEntryPage)
        self.assertCanNotCreateAt(BlogIndexPage, BlogEntryPage)

    def test_shipped_through_models_are_not_declared(self):
        self.assertFalse(hasattr(blog_models, "CategoryEntryPage"))
        self.assertFalse(hasattr(blog_models, "TagEntryPage"))
        tables = connection.introspection.table_names()
        self.assertNotIn("sites_conformes_blog_blogentrypage", tables)
        self.assertNotIn("sites_conformes_blog_categoryentrypage", tables)
        self.assertNotIn("sites_conformes_blog_tagentrypage", tables)

    def test_blog_index_lists_and_filters_custom_entries_by_category(self):
        entry = self.add_entry("en-bretagne")
        entry.categories.add(self.category)
        entry.tags.add("dsfr")
        entry.save()
        self.add_entry("ailleurs")

        response = self.client.get(self.blog.url + "?category=bretagne")

        self.assertEqual(list(response.context["posts"]), [entry])
        self.assertPageIsRenderable(entry)
