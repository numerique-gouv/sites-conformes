from django.contrib.auth import get_user_model
from django.urls import reverse
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.blog.tests.factories import BlogEntryPageFactory, BlogIndexPageFactory, CategoryFactory

User = get_user_model()


class BlogEntryPageAPITest(WagtailPageTestCase):
    def test_categories_are_exposed_under_their_historical_key(self):
        home = Page.objects.get(slug="home")
        admin = User.objects.create_superuser("test", "test@test.test", "pass")
        index = BlogIndexPageFactory(parent=home, owner=admin)
        category = CategoryFactory(locale=index.locale)
        entry = BlogEntryPageFactory(parent=index, owner=admin, categories=[category])

        response = self.client.get(reverse("wagtailapi:pages:detail", kwargs={"pk": entry.id}))

        self.assertEqual([c["slug"] for c in response.json()["blog_categories"]], [category.slug])
