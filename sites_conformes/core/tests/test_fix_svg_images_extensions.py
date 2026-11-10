from io import BytesIO, StringIO

from django.core.files.images import ImageFile
from django.core.management import call_command
from wagtail.images import get_image_model
from wagtail.test.utils import WagtailPageTestCase

Image = get_image_model()


class FixSvgImagesExtensionsTestCase(WagtailPageTestCase):
    def create_image(self, path, name):
        with open(path, "rb") as f:
            return Image.objects.create(title=name, file=ImageFile(BytesIO(f.read()), name=name))

    def test_svg_without_extension_is_renamed(self):
        image = self.create_image("sites_conformes/static/artwork/technical-error.svg", "pictogram")
        old_name = image.file.name

        call_command("fix_svg_images_extensions", stdout=StringIO())

        image.refresh_from_db()
        self.assertRegex(image.file.name, r"^original_images/pictogram[^/]*\.svg$")
        self.assertTrue(image.is_svg())
        self.assertTrue(image.file.storage.exists(image.file.name))
        self.assertFalse(image.file.storage.exists(old_name))

    def test_dry_run_keeps_the_file(self):
        image = self.create_image("sites_conformes/static/artwork/technical-error.svg", "pictogram")
        old_name = image.file.name

        call_command("fix_svg_images_extensions", "--dry-run", stdout=StringIO())

        image.refresh_from_db()
        self.assertEqual(image.file.name, old_name)

    def test_missing_file_does_not_abort(self):
        broken = self.create_image("sites_conformes/static/artwork/technical-error.svg", "broken")
        broken.file.storage.delete(broken.file.name)
        image = self.create_image("sites_conformes/static/artwork/technical-error.svg", "pictogram")

        call_command("fix_svg_images_extensions", stdout=StringIO(), stderr=StringIO())

        image.refresh_from_db()
        self.assertTrue(image.file.name.endswith(".svg"))
