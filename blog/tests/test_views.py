import zoneinfo
from datetime import datetime

from django.contrib.auth import get_user_model
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from blog.models import BlogEntryPage, BlogIndexPage, Person
from content_manager.models import ContentPage

User = get_user_model()


class BlogTestCase(WagtailPageTestCase):
    def setUp(self):
        self.home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()
        self.blog_index_page = self.home.add_child(
            instance=BlogIndexPage(
                title="Actualités",
                slug="actualités",
                owner=self.admin,
            )
        )
        self.blog_index_page.save()

        self.paris_tz = zoneinfo.ZoneInfo("Europe/Paris")
        self.blog_post = self.blog_index_page.add_child(
            instance=BlogEntryPage(
                title="J’accuse",
                date=datetime(1898, 6, 13, 6, 0, 0, tzinfo=self.paris_tz),
                owner=self.admin,
            )
        )

        self.emile = Person.objects.create(name="Émile Zola")
        self.blog_post.authors.add(self.emile)
        self.blog_post.save()

    def test_blog_index_page_is_renderable(self):
        self.assertPageIsRenderable(self.blog_index_page)

    def test_blog_index_page_has_minimal_content(self):
        response = self.client.get(self.blog_index_page.url)
        self.assertEqual(response.status_code, 200)

        self.assertInHTML(
            "<title>Actualités — Titre du site</title>",
            response.content.decode(),
        )

    def test_blog_index_page_has_posts(self):
        response = self.client.get(self.blog_index_page.url)

        self.assertContains(
            response,
            "J’accuse",
        )
        self.assertContains(
            response,
            "Publié le lundi 13 juin 1898",
        )

    def test_blog_post_is_renderable(self):
        self.assertPageIsRenderable(self.blog_post)

    def test_blog_post_has_minimal_content(self):
        response = self.client.get(self.blog_post.url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "<title>J’accuse — Titre du site</title>",
        )

    def test_blog_has_rss_feed(self):
        response = self.client.get(self.blog_index_page.url + "rss/")
        self.assertEqual(response.status_code, 200)

    def test_deep_blog_works(self):
        new_parent = self.home.add_child(
            instance=ContentPage(
                title="Page intermédiaire",
                owner=self.admin,
            )
        )
        deep_blog_index_page = new_parent.add_child(
            instance=BlogIndexPage(
                title="Nouveau blog",
                slug="nouveau-blog",
                owner=self.admin,
            )
        )
        deep_blog_index_page.save()

        new_blog_post = deep_blog_index_page.add_child(
            instance=BlogEntryPage(
                title="Livres d’aujourd’hui et de demain",
                date=datetime(1869, 9, 7, 6, 0, 0, tzinfo=self.paris_tz),
                owner=self.admin,
            )
        )
        new_blog_post.authors.add(self.emile)
        new_blog_post.save()

        self.assertPageIsRenderable(deep_blog_index_page)

        self.assertPageIsRenderable(new_blog_post)

        response = self.client.get(deep_blog_index_page.url + "rss/")
        self.assertEqual(response.status_code, 200)
