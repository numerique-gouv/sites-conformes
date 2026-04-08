from django.db import IntegrityError
from django.test import TestCase
from wagtail.models import Site
from wagtail.test.utils import WagtailPageTestCase

from menus.blocks import MainMenuStructValue, MainMenuSubmenuBlock
from menus.models import FooterBottomMenu, MainMenu, TopMenu


class TopMenuModelTestCase(WagtailPageTestCase):
    def setUp(self):
        self.site = Site.objects.get(is_default_site=True)

    def test_str(self):
        menu = TopMenu.objects.create(site=self.site)
        self.assertEqual(str(menu), f"Menu du haut pour le site {self.site.hostname}")

    def test_has_translation_key(self):
        menu = TopMenu.objects.create(site=self.site)
        self.assertIsNotNone(menu.translation_key)

    def test_unique_site_constraint(self):
        TopMenu.objects.create(site=self.site)
        with self.assertRaises(IntegrityError):
            TopMenu.objects.create(site=self.site)


class FooterBottomMenuModelTestCase(WagtailPageTestCase):
    def setUp(self):
        self.site = Site.objects.get(is_default_site=True)

    def test_str(self):
        menu = FooterBottomMenu.objects.create(site=self.site)
        self.assertEqual(str(menu), f"Menu du bas du pied de page pour le site {self.site.hostname}")

    def test_has_translation_key(self):
        menu = FooterBottomMenu.objects.create(site=self.site)
        self.assertIsNotNone(menu.translation_key)

    def test_unique_site_constraint(self):
        FooterBottomMenu.objects.create(site=self.site)
        with self.assertRaises(IntegrityError):
            FooterBottomMenu.objects.create(site=self.site)


class MainMenuModelTestCase(WagtailPageTestCase):
    def setUp(self):
        self.site = Site.objects.get(is_default_site=True)

    def test_str(self):
        menu = MainMenu.objects.create(site=self.site)
        self.assertEqual(str(menu), f"Menu principal pour le site {self.site.hostname}")

    def test_has_translation_key(self):
        menu = MainMenu.objects.create(site=self.site)
        self.assertIsNotNone(menu.translation_key)

    def test_unique_site_constraint(self):
        MainMenu.objects.create(site=self.site)
        with self.assertRaises(IntegrityError):
            MainMenu.objects.create(site=self.site)


class MainMenuStructValueTestCase(TestCase):
    def _make_struct_value(self, label, links=None, columns=None):
        """Helper to build a MainMenuStructValue-like dict for testing."""
        block = MainMenuSubmenuBlock()
        # Use dict-based StructValue for unit testing the methods directly
        value = MainMenuStructValue(
            block,
            [
                ("label", label),
                ("links", links or []),
                ("columns", columns or []),
            ],
        )
        return value

    def test_id_with_plain_label(self):
        value = self._make_struct_value("Mon menu")
        self.assertEqual(value.id(), "collapse-menu-mon-menu")

    def test_id_with_special_characters(self):
        value = self._make_struct_value("Actualités & Événements")
        # slugify strips accents and special chars
        self.assertEqual(value.id(), "collapse-menu-actualites-evenements")
