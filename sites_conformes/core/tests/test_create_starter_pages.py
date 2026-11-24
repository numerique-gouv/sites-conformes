from io import StringIO
from unittest import mock

from django.core.management import call_command
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.utils import get_default_site
from sites_conformes.menus.models import FooterBottomMenu


def skip_image_imports(name, *args, **kwargs):
    if name not in ("import_dsfr_pictograms", "import_illustration_images"):
        call_command(name, *args, **kwargs)


@mock.patch("sites_conformes.core.management.commands.create_starter_pages.call_command", skip_image_imports)
class CreateStarterPagesTestCase(WagtailPageTestCase):
    def test_footer_menu_links_to_the_legal_pages(self):
        call_command("create_starter_pages", stdout=StringIO())

        footer_menu = FooterBottomMenu.objects.get(site=get_default_site())
        self.assertEqual(
            [(item.value["text"], item.value["page"].slug) for item in footer_menu.items],
            [("Mentions légales", "mentions-legales"), ("Accessibilité\xa0: non conforme", "accessibilite")],
        )
