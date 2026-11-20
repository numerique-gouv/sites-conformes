from wagtail.images import get_image_model
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.utils import import_image

Image = get_image_model()


class UtilsTestCase(WagtailPageTestCase):
    def test_import_image(self):
        image_file = "sites_conformes/static/artwork/technical-error.svg"
        image = import_image(image_file, "Sample image")

        assert isinstance(image, Image)
        assert image.title == "Sample image"
        assert image.file.name.endswith(".svg")

    def test_import_image_names_the_file_after_its_title(self):
        # Exports detect pictograms by "Pictogrammes_DSFR" in their file name
        image = import_image(
            "sites_conformes/static/artwork/technical-error.svg", "Pictogrammes DSFR — System — Technical Error"
        )

        self.assertRegex(image.file.name, r"^original_images/Pictogrammes_DSFR__System__Technical_Error[^/]*\.svg$")
