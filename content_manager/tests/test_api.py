from django.contrib.auth import get_user_model
from django.urls import reverse
from wagtail.models import Page
from wagtail.rich_text import RichText
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.content_manager.models import ContentPage

User = get_user_model()


class APITestCase(WagtailPageTestCase):
    def setUp(self):
        home_page = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()

        self.lorem_raw = "<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>"
        lorem_body = []
        lorem_body.append(("paragraph", RichText(self.lorem_raw)))

        self.content_page = home_page.add_child(
            instance=ContentPage(title="Sample page", slug="content-page", owner=self.admin, body=lorem_body)
        )
        self.content_page.save()

    def test_published_page_api_is_visible(self):
        url = reverse("wagtailapi:pages:detail", kwargs={"pk": self.content_page.id})
        response = self.client.get(url)

        self.assertEqual(self.lorem_raw, response.json()["body"][0]["value"])

    def test_draft_page_api_is_not_visible(self):
        self.content_page.live = False
        self.content_page.save()
        url = reverse("wagtailapi:pages:detail", kwargs={"pk": self.content_page.id})
        response = self.client.get(url)

        self.assertEqual({"message": "No Page matches the given query."}, response.json())
