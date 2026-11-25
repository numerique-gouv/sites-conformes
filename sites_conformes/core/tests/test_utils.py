from wagtail.images import get_image_model
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.constants import EXAMPLE_IMAGE_ERROR_PATH
from sites_conformes.core.utils import import_image

Image = get_image_model()


class UtilsTestCase(WagtailPageTestCase):
    def test_import_image(self):
        image_file = EXAMPLE_IMAGE_ERROR_PATH
        image = import_image(image_file, "Sample image")

        assert isinstance(image, Image)
        assert image.title == "Sample image"
