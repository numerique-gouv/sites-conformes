from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from wagtail.models import Page
from wagtail.rich_text import RichText
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.blog.models import BlogEntryPage, BlogIndexPage

User = get_user_model()


class BlogSearchResultsTestCase(WagtailPageTestCase):
    def setUp(self):
        home_page = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")

        # Common body for the two pages
        body = []

        text_raw = """<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>"""
        body.append(("paragraph", RichText(text_raw)))

        self.admin.save()
        self.blog_index = home_page.add_child(
            instance=BlogIndexPage(
                title="Index de blog",
                body=body,
                slug="blog-index",
                owner=self.admin,
            )
        )
        self.blog_index.save_revision().publish()

        self.blog_entry = self.blog_index.add_child(
            instance=BlogEntryPage(
                title="Page de blog",
                body=body,
                slug="blog-entry",
                owner=self.admin,
            )
        )
        self.blog_entry.save_revision().publish()

        call_command("update_index")

    def test_search_blog_index_is_found(self):
        search_url = reverse("cms_search")
        response = self.client.get(f"{search_url}?q=Lorem")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Index de blog")

    def test_search_blog_entry_is_found(self):
        search_url = reverse("cms_search")
        response = self.client.get(f"{search_url}?q=Lorem")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page de blog")
