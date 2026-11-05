from types import SimpleNamespace

from django.test import SimpleTestCase
from wagtail.images import get_image_model
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.utils import get_closest_image_ratio, import_image

Image = get_image_model()


class UtilsTestCase(WagtailPageTestCase):
    def test_import_image(self):
        image_file = "sites_conformes/static/artwork/technical-error.svg"
        image = import_image(image_file, "Sample image")

        assert isinstance(image, Image)
        assert image.title == "Sample image"


class ClosestImageRatioTestCase(SimpleTestCase):
    def test_closest_dsfr_ratio_is_chosen(self):
        for (width, height), expected in [
            ((1200, 800), "fr-ratio-3x2"),
            ((1200, 932), "fr-ratio-4x3"),
            ((1200, 865), "fr-ratio-4x3"),
            ((959, 1200), "fr-ratio-3x4"),
            ((800, 800), "fr-ratio-1x1"),
            ((1920, 1080), "fr-ratio-16x9"),
        ]:
            with self.subTest(width=width, height=height):
                image = SimpleNamespace(width=width, height=height)
                self.assertEqual(get_closest_image_ratio(image), expected)
