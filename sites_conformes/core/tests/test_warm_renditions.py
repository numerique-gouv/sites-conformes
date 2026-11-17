from io import StringIO

from django.core.management import call_command
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.models import ContentPage
from sites_conformes.core.utils import import_image


class RenditionsCommandsTestCase(WagtailPageTestCase):
    def setUp(self):
        self.image = import_image(
            "sites_conformes/static/illustration/illustration-sites-faciles-homme-nuages.png", "Homme nuages"
        )
        value = {"image": {"image": self.image, "alt_text": "", "decorative": True}, "width": "", "image_ratio": ""}
        Page.objects.get(slug="home").add_child(
            instance=ContentPage(title="Image", slug="image", body=[("image", value)])
        )

    def webp_renditions(self):
        return self.image.renditions.filter(filter_spec__contains="format-webp")

    def test_warming_renders_live_pages_and_reports_what_it_created(self):
        # Publishing already renders the page, so start from a page saved before the deploy
        self.image.renditions.all().delete()

        stdout = StringIO()
        call_command("warm_renditions", stdout=stdout, stderr=StringIO())

        self.assertTrue(self.webp_renditions().exists())
        self.assertRegex(stdout.getvalue(), r"0 errors, [1-9]\d* renditions created in \d+\.\d s")

    def test_cooling_deletes_only_the_webp_renditions(self):
        self.image.get_rendition("width-100")
        self.image.get_rendition("width-100|format-webp")
        webp_file = self.webp_renditions().first().file
        storage, name = webp_file.storage, webp_file.name

        # Wagtail deletes the files once the transaction is committed
        with self.captureOnCommitCallbacks(execute=True):
            call_command("cool_renditions", stdout=StringIO())

        self.assertFalse(self.webp_renditions().exists())
        self.assertFalse(storage.exists(name))
        self.assertTrue(self.image.renditions.filter(filter_spec="width-100").exists())

    def test_cooling_dry_run_deletes_nothing(self):
        self.image.get_rendition("width-100|format-webp")

        stdout = StringIO()
        call_command("cool_renditions", "--dry-run", stdout=stdout)

        self.assertTrue(self.webp_renditions().exists())
        self.assertIn("would be deleted", stdout.getvalue())
