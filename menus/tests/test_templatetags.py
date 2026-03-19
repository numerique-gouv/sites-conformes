from django.template import Context
from django.test import RequestFactory
from django.utils.translation import override
from wagtail.models import Locale, Site
from wagtail.test.utils import WagtailPageTestCase

from menus.models import FooterBottomMenu, MainMenu, TopMenu
from menus.templatetags.wagtail_dsfr_menus_tags import footer_bottom_menu, main_menu, top_menu


class BaseMenuLocaleTestCase(WagtailPageTestCase):
    def setUp(self):
        self.site = Site.objects.get(is_default_site=True)
        self.factory = RequestFactory()
        self.locale_fr = Locale.objects.get(language_code="fr")
        self.locale_en, _ = Locale.objects.get_or_create(language_code="en")

    def _make_context(self):
        request = self.factory.get("/", SERVER_NAME=self.site.hostname)
        return Context({"request": request})


class TopMenuTagLocaleTestCase(BaseMenuLocaleTestCase):
    def setUp(self):
        super().setUp()
        self.menu_fr = TopMenu.objects.create(site=self.site, locale=self.locale_fr)
        self.menu_en = TopMenu.objects.create(site=self.site, locale=self.locale_en)

    def test_returns_menu_in_active_locale(self):
        with override("en"):
            result = top_menu(self._make_context())
        self.assertEqual(result["top_menu"], self.menu_en)

    def test_returns_default_locale_menu_for_default_language(self):
        with override("fr"):
            result = top_menu(self._make_context())
        self.assertEqual(result["top_menu"], self.menu_fr)

    def test_falls_back_to_any_menu_when_no_translation_exists(self):
        self.menu_en.delete()
        with override("en"):
            result = top_menu(self._make_context())
        self.assertEqual(result["top_menu"], self.menu_fr)


class FooterBottomMenuTagLocaleTestCase(BaseMenuLocaleTestCase):
    def setUp(self):
        super().setUp()
        self.menu_fr = FooterBottomMenu.objects.create(site=self.site, locale=self.locale_fr)
        self.menu_en = FooterBottomMenu.objects.create(site=self.site, locale=self.locale_en)

    def test_returns_menu_in_active_locale(self):
        with override("en"):
            result = footer_bottom_menu(self._make_context())
        self.assertEqual(result["footer_bottom_menu"], self.menu_en)

    def test_returns_default_locale_menu_for_default_language(self):
        with override("fr"):
            result = footer_bottom_menu(self._make_context())
        self.assertEqual(result["footer_bottom_menu"], self.menu_fr)

    def test_falls_back_to_any_menu_when_no_translation_exists(self):
        self.menu_en.delete()
        with override("en"):
            result = footer_bottom_menu(self._make_context())
        self.assertEqual(result["footer_bottom_menu"], self.menu_fr)


class MainMenuTagLocaleTestCase(BaseMenuLocaleTestCase):
    def setUp(self):
        super().setUp()
        self.menu_fr = MainMenu.objects.create(site=self.site, locale=self.locale_fr)
        self.menu_en = MainMenu.objects.create(site=self.site, locale=self.locale_en)

    def test_returns_menu_in_active_locale(self):
        with override("en"):
            result = main_menu(self._make_context())
        self.assertEqual(result["main_menu"], self.menu_en)

    def test_returns_default_locale_menu_for_default_language(self):
        with override("fr"):
            result = main_menu(self._make_context())
        self.assertEqual(result["main_menu"], self.menu_fr)

    def test_falls_back_to_any_menu_when_no_translation_exists(self):
        self.menu_en.delete()
        with override("en"):
            result = main_menu(self._make_context())
        self.assertEqual(result["main_menu"], self.menu_fr)
