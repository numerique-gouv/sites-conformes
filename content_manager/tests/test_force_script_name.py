from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.content_manager.models import ContentPage

User = get_user_model()


class ContentPageTestCase(WagtailPageTestCase):

    def setUp(self):
        home_page = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()
        self.content_page = home_page.add_child(
            instance=ContentPage(
                title="Page de contenu",
                slug="content-page",
                owner=self.admin,
            )
        )
        self.content_page.save()

    @override_settings(
        FORCE_SCRIPT_NAME="/test_subpath", MEDIA_URL="/test_subpath/medias/", STATIC_URL="/test_subpath/static/"
    )
    def test_page_renders_subpath(self):
        content_page_url = self.content_page.get_url()

        response = self.client.get(content_page_url)

        self.assertEqual(response.status_code, 200)

        self.assertInHTML(
            """<link rel="canonical" href="http://localhost/test_subpath/content-page/" />""",
            response.content.decode(),
        )
        self.assertInHTML(
            """<link rel="apple-touch-icon" href="/test_subpath/static/dsfr/dist/favicon/apple-touch-icon.png" />""",
            response.content.decode(),
        )

        self.assertInHTML(
            """<meta property="og:url" content="http://localhost/test_subpath/content-page/" />""",
            response.content.decode(),
        )

        self.assertInHTML(
            """
              <a href="/test_subpath/" title="Accueil — Titre du site">
                <p class="fr-header__service-title">Titre du site</p>
              </a>
            """,
            response.content.decode(),
        )
