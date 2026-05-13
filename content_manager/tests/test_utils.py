from wagtail.images.models import Image
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.content_manager.utils import import_image


class UtilsTestCase(WagtailPageTestCase):
    def test_import_image(self):
        image_file = "static/artwork/technical-error.svg"
        image = import_image(image_file, "Sample image")

        assert isinstance(image, Image)
        assert image.title == "Sample image"
