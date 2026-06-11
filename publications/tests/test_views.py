import zoneinfo
from datetime import datetime

from django.contrib.auth import get_user_model
from wagtail.models import Page

from publications.models import PublicationIndexPage, PublicationPage
from sites_conformes.blog.models import Person
from sites_conformes.blog.tests.test_views import BlogTestCase
from sites_conformes.core.models import ContentPage

User = get_user_model()


class PublicationTestCase(BlogTestCase):
    """Reuses BlogTestCase tests through inheritance. Also copies what can't
    be inherited : setUp and test_deep_blog_works"""

    def setUp(self):
        self.home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()
        self.blog_index_page = self.home.add_child(
            instance=PublicationIndexPage(
                title="Actualités",
                slug="actualités",
                owner=self.admin,
            )
        )
        self.blog_index_page.save()

        self.paris_tz = zoneinfo.ZoneInfo("Europe/Paris")
        self.blog_post = self.blog_index_page.add_child(
            instance=PublicationPage(
                title="J’accuse",
                date=datetime(1898, 6, 13, 6, 0, 0, tzinfo=self.paris_tz),
                owner=self.admin,
            )
        )

        self.emile = Person.objects.create(name="Émile Zola")
        self.blog_post.authors.add(self.emile)
        self.blog_post.save()

    def test_deep_blog_works(self):
        new_parent = self.home.add_child(
            instance=ContentPage(
                title="Page intermédiaire",
                owner=self.admin,
            )
        )
        deep_blog_index_page = new_parent.add_child(
            instance=PublicationIndexPage(
                title="Nouveau blog",
                slug="nouveau-blog",
                owner=self.admin,
            )
        )
        deep_blog_index_page.save()

        new_blog_post = deep_blog_index_page.add_child(
            instance=PublicationPage(
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
