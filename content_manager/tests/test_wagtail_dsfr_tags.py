from django.template import Context
from django.test import RequestFactory
from django.utils.translation import override
from wagtail.models import Locale, Page, Site
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.content_manager.models import CmsDsfrConfig, ContentPage, LanguageSelectorItem


class LanguageSelectorTagBaseTestCase(WagtailPageTestCase):
    def setUp(self):
        self.site = Site.objects.get(is_default_site=True)
        self.home_page = Page.objects.get(slug="home")
        self.content_page = self.home_page.add_child(instance=ContentPage(title="Page de test", slug="test-page"))
        self.content_page.save()
        self.config, _ = CmsDsfrConfig.objects.update_or_create(site_id=self.site.id, defaults={})
        self.factory = RequestFactory()

    def _make_context(self):
        request = self.factory.get("/", SERVER_NAME=self.site.hostname)
        return Context({"request": request})


class LanguageSelectorTagDisabledTestCase(LanguageSelectorTagBaseTestCase):
    def setUp(self):
        super().setUp()
        self.config.language_selector_mode = "disabled"
        self.config.save()

    def test_is_not_active(self):
        from sites_conformes.content_manager.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        self.assertFalse(result["language_selector"]["is_active"])

    def test_items_are_empty(self):
        from sites_conformes.content_manager.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        self.assertEqual(result["language_selector"]["items"], [])

    def test_widget_not_rendered(self):
        response = self.client.get(self.content_page.url)
        self.assertNotContains(response, "fr-translate")


class LanguageSelectorTagSimpleTestCase(LanguageSelectorTagBaseTestCase):
    def setUp(self):
        super().setUp()
        self.locale_fr = Locale.objects.get(language_code="fr")
        self.locale_en, _ = Locale.objects.get_or_create(language_code="en")
        self.config.language_selector_mode = "simple"
        self.config.save()

        with override("fr"):
            self.home_en = self.home_page.copy_for_translation(locale=self.locale_en)
            self.home_en.slug = "home-en"
            self.home_en.save_revision().publish()

    def test_is_active(self):
        from sites_conformes.content_manager.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        self.assertTrue(result["language_selector"]["is_active"])

    def test_items_include_default_locale(self):
        from sites_conformes.content_manager.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        codes = [item["language_code"] for item in result["language_selector"]["items"]]
        self.assertIn("fr", codes)

    def test_items_include_translated_locale(self):
        from sites_conformes.content_manager.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        codes = [item["language_code"] for item in result["language_selector"]["items"]]
        self.assertIn("en", codes)

    def test_items_include_homepage_url(self):
        from sites_conformes.content_manager.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        urls = [item["url"] for item in result["language_selector"]["items"]]
        self.assertIn(self.home_page.full_url, urls)

    def test_widget_rendered(self):
        response = self.client.get(self.content_page.url)
        self.assertContains(response, "fr-translate")


class LanguageSelectorTagManualTestCase(LanguageSelectorTagBaseTestCase):
    def setUp(self):
        super().setUp()
        self.config.language_selector_mode = "manual"
        self.config.save()

        self.fr_page = self.home_page.add_child(instance=ContentPage(title="Page FR", slug="page-fr"))
        self.fr_page.save()

        LanguageSelectorItem.objects.create(
            site_config=self.config,
            language_code="fr",
            language_name="Français",
            page=self.fr_page,
        )
        LanguageSelectorItem.objects.create(
            site_config=self.config,
            language_code="en",
            language_name="English",
            external_url="https://en.example.com",
        )

    def test_is_active(self):
        from sites_conformes.content_manager.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        self.assertTrue(result["language_selector"]["is_active"])

    def test_page_item_uses_page_full_url(self):
        from sites_conformes.content_manager.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        fr_item = next(i for i in result["language_selector"]["items"] if i["language_code"] == "fr")
        self.assertEqual(fr_item["url"], self.fr_page.full_url)

    def test_external_url_item(self):
        from sites_conformes.content_manager.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        en_item = next(i for i in result["language_selector"]["items"] if i["language_code"] == "en")
        self.assertEqual(en_item["url"], "https://en.example.com")

    def test_item_language_name(self):
        from sites_conformes.content_manager.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        en_item = next(i for i in result["language_selector"]["items"] if i["language_code"] == "en")
        self.assertEqual(en_item["language_name"], "English")

    def test_widget_rendered_with_links(self):
        response = self.client.get(self.content_page.url)
        html = response.content.decode()
        self.assertInHTML(
            '<a class="fr-translate__language fr-nav__link"'
            ' hreflang="en" lang="en" href="https://en.example.com">'
            "EN - English"
            "</a>",
            html,
        )

    def test_widget_rendered_with_page_link(self):
        response = self.client.get(self.content_page.url)
        html = response.content.decode()
        self.assertInHTML(
            f'<a class="fr-translate__language fr-nav__link"'
            f' hreflang="fr" lang="fr" href="{self.fr_page.full_url}"'
            f' aria-current="true">'
            "FR - Français"
            "</a>",
            html,
        )
