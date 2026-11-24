from io import StringIO
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.models import ContentPage
from sites_conformes.core.utils import get_default_site
from sites_conformes.forms.models import FormPage
from sites_conformes.menus.models import FooterBottomMenu, MainMenu


def skip_image_imports(name, *args, **kwargs):
    if name not in ("import_dsfr_pictograms", "import_illustration_images"):
        call_command(name, *args, **kwargs)


def get_menu_items(menu) -> list:
    # Without the block ids, generated when the menu is loaded
    return [(block["type"], block["value"]) for block in menu.items.raw_data]


def create_starter_pages(**kwargs) -> str:
    stdout = StringIO()
    call_command("create_starter_pages", stdout=stdout, **kwargs)
    return stdout.getvalue()


@mock.patch("sites_conformes.core.management.commands.create_starter_pages.call_command", skip_image_imports)
class CreateStarterPagesTestCase(WagtailPageTestCase):
    def test_new_instance_gets_a_home_page_and_its_subpages(self):
        create_starter_pages()

        site = get_default_site()
        home = site.root_page.specific
        self.assertIsInstance(home, ContentPage)
        self.assertEqual(home.slug, "home")
        self.assertEqual(home.title, "Votre nouveau site avec Sites Conformes")
        self.assertEqual(
            sorted(home.get_children().values_list("slug", flat=True)),
            ["accessibilite", "contact", "mentions-legales"],
        )
        # The initial Wagtail page is replaced
        self.assertEqual(Page.objects.filter(depth=2).count(), 1)
        self.assertEqual(site.hostname, settings.HOST_URL)

    def test_contact_page_is_a_form(self):
        create_starter_pages()

        contact_page = Page.objects.get(slug="contact").specific
        self.assertIsInstance(contact_page, FormPage)
        self.assertTrue(contact_page.form_fields.exists())

    def test_main_menu_links_to_the_home_and_contact_pages(self):
        create_starter_pages()

        main_menu = MainMenu.objects.get(site=get_default_site())
        self.assertEqual([item.value["page"].slug for item in main_menu.items], ["home", "contact"])

    def test_footer_menu_links_to_the_legal_pages(self):
        create_starter_pages()

        footer_menu = FooterBottomMenu.objects.get(site=get_default_site())
        self.assertEqual(
            [(item.value["text"], item.value["page"].slug) for item in footer_menu.items],
            [("Mentions légales", "mentions-legales"), ("Accessibilité\xa0: non conforme", "accessibilite")],
        )

    def test_instance_with_pages_is_unchanged(self):
        # The command runs at each deployment
        create_starter_pages()
        pages = list(Page.objects.order_by("pk").values_list("pk", "slug"))
        footer_items = get_menu_items(FooterBottomMenu.objects.get(site=get_default_site()))

        output = create_starter_pages()

        self.assertIn("already have pages", output)
        self.assertEqual(list(Page.objects.order_by("pk").values_list("pk", "slug")), pages)
        self.assertEqual(get_menu_items(FooterBottomMenu.objects.get(site=get_default_site())), footer_items)

    def test_slug_parameter_creates_a_missing_page_only(self):
        create_starter_pages()
        Page.objects.get(slug="mentions-legales").delete()
        count = Page.objects.count()

        create_starter_pages(slug=["mentions-legales", "contact"])

        self.assertEqual(Page.objects.count(), count + 1)
        self.assertEqual(Page.objects.get(slug="mentions-legales").get_parent().pk, get_default_site().root_page_id)
        self.assertEqual(Page.objects.filter(slug="contact").count(), 1)

    def test_unknown_slug_is_refused(self):
        with self.assertRaises(CommandError):
            call_command("create_starter_pages", "--slug", "inconnue", stdout=StringIO())
