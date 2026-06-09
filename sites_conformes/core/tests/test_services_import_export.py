from django.core.management import call_command
from django.test import SimpleTestCase
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.models import ContentPage
from sites_conformes.core.utils import guess_extension


class ImportPagesTestCase(WagtailPageTestCase):
    def setUp(self):
        call_command("create_starter_pages")
        call_command("import_page_templates")
        self.templates_index = ContentPage.objects.get(slug="page_templates_index")
        self.home_page = ContentPage.objects.get(slug="home")

    def test_copied_template_is_correctly_updated(self):
        template = ContentPage.objects.child_of(self.templates_index).first()
        new_page = template.copy(to=self.home_page)

        self.assertEqual(new_page.get_parent(), self.home_page)
        self.assertEqual(new_page.source_url, None)

        find_template = (
            ContentPage.objects.child_of(self.templates_index).filter(source_url=template.source_url).first()
        )
        self.assertEqual(template.id, find_template.id)


class GuessExtensionTestCase(SimpleTestCase):
    """Unit tests for guess_extension — no DB required."""

    def _call(self, filename, content=b""):
        return guess_extension(filename, content)

    def test_svg_extension_preserved(self):
        self.assertEqual(self._call("icon.svg"), ".svg")

    def test_png_extension_preserved(self):
        self.assertEqual(self._call("photo.PNG"), ".png")

    def test_jpg_extension_preserved(self):
        self.assertEqual(self._call("photo.jpg"), ".jpg")

    def test_sniff_png(self):
        self.assertEqual(self._call("image", b"\x89PNG rest of header"), ".png")

    def test_sniff_jpg(self):
        self.assertEqual(self._call("image", b"\xff\xd8\xff rest"), ".jpg")

    def test_sniff_gif87(self):
        self.assertEqual(self._call("image", b"GIF87a rest"), ".gif")

    def test_sniff_gif89(self):
        self.assertEqual(self._call("image", b"GIF89a rest"), ".gif")

    def test_sniff_webp(self):
        self.assertEqual(self._call("image", b"RIFF\x00\x00\x00\x00WEBP rest"), ".webp")

    def test_sniff_avif(self):
        # ISOBMFF: 4-byte box size, "ftyp" box type, then the "avif" brand.
        self.assertEqual(self._call("image", b"\x00\x00\x00\x20ftypavif rest"), ".avif")

    def test_sniff_avif_sequence_brand(self):
        self.assertEqual(self._call("image", b"\x00\x00\x00\x20ftypavis rest"), ".avif")

    def test_sniff_svg(self):
        svg = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
        self.assertEqual(self._call("image", svg), ".svg")

    def test_sniff_svg_uppercase_tag(self):
        # The check lowercases the bytes before searching
        svg = b"<SVG xmlns='http://www.w3.org/2000/svg'></SVG>"
        self.assertEqual(self._call("image", svg), ".svg")

    def test_unknown_content_returns_empty(self):
        self.assertEqual(self._call("image", b"\x00\x01\x02\x03"), "")
