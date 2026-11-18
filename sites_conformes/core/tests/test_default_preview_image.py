from django.contrib.auth import get_user_model
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Page, Site
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.models import CmsDsfrConfig, ContentPage

User = get_user_model()
Image = get_image_model()


class DefaultPreviewImageTestCase(WagtailPageTestCase):
    def setUp(self):
        home_page = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.page = home_page.add_child(instance=ContentPage(title="Page de contenu", slug="content-page"))
        self.config, _ = CmsDsfrConfig.objects.update_or_create(site_id=Site.objects.get().id, defaults={})
        self.default_image = Image.objects.create(title="Default share image", file=get_test_image_file())

    def get_meta(self):
        return self.client.get(self.page.url).content.decode()

    def set_default_preview_image(self):
        self.config.default_preview_image = self.default_image
        self.config.save()

    def test_no_preview_image_by_default(self):
        content = self.get_meta()

        self.assertInHTML('<meta name="twitter:card" content="summary" />', content)
        self.assertNotIn('property="og:image"', content)

    def test_default_preview_image_is_used_as_fallback(self):
        self.set_default_preview_image()

        content = self.get_meta()

        self.assertInHTML('<meta name="twitter:card" content="summary_large_image" />', content)
        rendition = self.default_image.get_rendition("fill-1200x630")
        self.assertInHTML(f'<meta property="og:image" content="{rendition.full_url}" />', content)

    def test_page_preview_image_wins_over_the_default(self):
        self.set_default_preview_image()
        page_image = Image.objects.create(title="Page share image", file=get_test_image_file())
        self.page.preview_image = page_image
        self.page.save_revision().publish()

        content = self.get_meta()

        rendition = page_image.get_rendition("fill-1200x630")
        self.assertInHTML(f'<meta property="og:image" content="{rendition.full_url}" />', content)
        self.assertNotIn(self.default_image.get_rendition("fill-1200x630").url, content)
