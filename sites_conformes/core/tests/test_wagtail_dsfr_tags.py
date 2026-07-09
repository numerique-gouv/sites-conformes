from django.template import Context
from django.test import RequestFactory, SimpleTestCase
from django.utils.translation import override
from wagtail.models import Locale, Page, Site
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.models import CmsDsfrConfig, ContentPage, LanguageSelectorItem
from sites_conformes.core.templatetags.wagtail_dsfr_tags import toggle_url_filter


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
        from sites_conformes.core.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        self.assertFalse(result["language_selector"]["is_active"])

    def test_items_are_empty(self):
        from sites_conformes.core.templatetags.wagtail_dsfr_tags import language_selector

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
        from sites_conformes.core.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        self.assertTrue(result["language_selector"]["is_active"])

    def test_items_include_default_locale(self):
        from sites_conformes.core.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        codes = [item["language_code"] for item in result["language_selector"]["items"]]
        self.assertIn("fr", codes)

    def test_items_include_translated_locale(self):
        from sites_conformes.core.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        codes = [item["language_code"] for item in result["language_selector"]["items"]]
        self.assertIn("en", codes)

    def test_items_include_homepage_url(self):
        from sites_conformes.core.templatetags.wagtail_dsfr_tags import language_selector

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
        from sites_conformes.core.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        self.assertTrue(result["language_selector"]["is_active"])

    def test_page_item_uses_page_full_url(self):
        from sites_conformes.core.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        fr_item = next(i for i in result["language_selector"]["items"] if i["language_code"] == "fr")
        self.assertEqual(fr_item["url"], self.fr_page.full_url)

    def test_external_url_item(self):
        from sites_conformes.core.templatetags.wagtail_dsfr_tags import language_selector

        result = language_selector(self._make_context())
        en_item = next(i for i in result["language_selector"]["items"] if i["language_code"] == "en")
        self.assertEqual(en_item["url"], "https://en.example.com")

    def test_item_language_name(self):
        from sites_conformes.core.templatetags.wagtail_dsfr_tags import language_selector

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


class ToggleUrlFilterTestBase(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _context(self, query_string="", **current):
        path = f"/?{query_string}" if query_string else "/"
        return {"request": self.factory.get(path), **current}


class ToggleUrlFilterBaselineTest(ToggleUrlFilterTestBase):
    def test_returns_empty_string_with_no_params(self):
        result = toggle_url_filter(self._context())
        self.assertEqual(result, "")

    def test_preserves_unrelated_get_params(self):
        result = toggle_url_filter(self._context("page=2"))
        self.assertEqual(result, "?page=2")


class ToggleUrlFilterAddFilterTest(ToggleUrlFilterTestBase):
    def test_adds_category_filter(self):
        category = type("Category", (), {"slug": "agriculture"})()
        result = toggle_url_filter(self._context(), category=category)
        self.assertEqual(result, "?category=agriculture")

    def test_adds_tag_filter(self):
        tag = type("Tag", (), {"slug": "news"})()
        result = toggle_url_filter(self._context(), tag=tag)
        self.assertEqual(result, "?tag=news")

    def test_adds_author_filter(self):
        author = type("Author", (), {"id": 7})()
        result = toggle_url_filter(self._context(), author=author)
        self.assertEqual(result, "?author=7")

    def test_adds_source_filter(self):
        source = type("Source", (), {"slug": "inrae"})()
        result = toggle_url_filter(self._context(), source=source)
        self.assertEqual(result, "?source=inrae")

    def test_adds_year_filter(self):
        result = toggle_url_filter(self._context(), year=2024)
        self.assertEqual(result, "?year=2024")

    def test_adds_filter_while_keeping_existing_params(self):
        author = type("Author", (), {"id": 3})()
        result = toggle_url_filter(self._context("tag=old"), author=author)
        self.assertEqual(result, "?tag=old&author=3")


class ToggleUrlFilterToggleOffTest(ToggleUrlFilterTestBase):
    def test_removes_active_category_when_it_is_the_only_param(self):
        category = type("Category", (), {"slug": "agriculture"})()
        result = toggle_url_filter(
            self._context("category=agriculture", current_category=category),
            category=category,
        )
        self.assertEqual(result, "")

    def test_removes_active_tag_when_it_is_the_only_param(self):
        tag = type("Tag", (), {"slug": "news"})()
        result = toggle_url_filter(
            self._context("tag=news", current_tag=tag),
            tag=tag,
        )
        self.assertEqual(result, "")

    def test_removes_active_tag_while_keeping_other_params(self):
        tag = type("Tag", (), {"slug": "news"})()
        result = toggle_url_filter(
            self._context("tag=news&author=3", current_tag=tag),
            tag=tag,
        )
        self.assertEqual(result, "?author=3")


class ToggleUrlFilterReplaceFilterTest(ToggleUrlFilterTestBase):
    def test_replaces_tag_with_different_value(self):
        current = type("Tag", (), {"slug": "old"})()
        new_tag = type("Tag", (), {"slug": "new"})()
        result = toggle_url_filter(
            self._context("tag=old", current_tag=current),
            tag=new_tag,
        )
        self.assertEqual(result, "?tag=new")


class ToggleUrlFilterFiltersDictTest(ToggleUrlFilterTestBase):
    def test_uses_filters_dict_instead_of_request_get(self):
        tag = type("Tag", (), {"slug": "news"})()
        result = toggle_url_filter(
            self._context("ignored=1"),
            filters_dict={"author": "7"},
            tag=tag,
        )
        self.assertEqual(result, "?author=7&tag=news")

    def test_empty_filters_dict_falls_back_to_request_get(self):
        author = type("Author", (), {"id": 3})()
        result = toggle_url_filter(
            self._context("tag=news"),
            filters_dict={},
            author=author,
        )
        self.assertEqual(result, "?tag=news&author=3")
