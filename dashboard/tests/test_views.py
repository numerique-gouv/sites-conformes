from django.contrib.auth import get_user_model
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.content_manager.models import ContentPage

User = get_user_model()


class DashboardTestCase(WagtailPageTestCase):
    def setUp(self):
        home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()

        self.content_page = home.add_child(
            instance=ContentPage(
                title="Page de contenu",
                slug="content-page",
                owner=self.admin,
            )
        )
        self.content_page.save()

    def test_userbar_is_present_when_logged_in(self):
        url = self.content_page.url
        response = self.client.get(url)
        self.assertNotContains(
            response,
            '<svg class="icon icon-edit w-userbar-icon" aria-hidden="true"><use href="#icon-edit"></use></svg>',
            html=True,
        )

        self.client.force_login(self.admin)
        response = self.client.get(url)
        self.assertContains(
            response,
            '<svg class="icon icon-edit w-userbar-icon" aria-hidden="true"><use href="#icon-edit"></use></svg>',
            html=True,
        )
