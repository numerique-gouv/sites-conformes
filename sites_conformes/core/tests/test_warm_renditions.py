from io import StringIO

from django.core.management import call_command
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.models import ContentPage
from sites_conformes.core.utils import import_image


class WarmRenditionsTestCase(WagtailPageTestCase):
    def test_rendering_live_pages_creates_their_renditions(self):
        image = import_image(
            "sites_conformes/static/illustration/illustration-sites-faciles-homme-nuages.png", "Homme nuages"
        )
        value = {"image": {"image": image, "alt_text": "", "decorative": True}, "width": "", "image_ratio": ""}
        Page.objects.get(slug="home").add_child(
            instance=ContentPage(title="Image", slug="image", body=[("image", value)])
        )
        # Publishing already renders the page, so start from a page saved before the deploy
        image.renditions.all().delete()

        stdout = StringIO()
        call_command("warm_renditions", stdout=stdout, stderr=StringIO())

        self.assertTrue(image.renditions.filter(filter_spec__contains="format-webp").exists())
        self.assertIn("0 errors", stdout.getvalue())
