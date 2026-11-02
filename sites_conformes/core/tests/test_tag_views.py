from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.models import CmsDsfrConfig, ContentPage, LanguageSelectorItem, Tag


class GlobalTagViewsTestCase(WagtailPageTestCase):
    def setUp(self):
        home = Page.objects.get(slug="home")
        self.tag = Tag.objects.create(name="Éducation", slug="education")

        self.tagged_page = home.add_child(instance=ContentPage(title="Page étiquetée", slug="page-etiquetee"))
        self.tagged_page.tags.add(self.tag)
        self.tagged_page.save_revision().publish()

        self.draft_page = home.add_child(
            instance=ContentPage(title="Brouillon étiqueté", slug="brouillon", live=False)
        )
        self.draft_page.tags.add(self.tag)
        self.draft_page.save()

    def test_tags_list(self):
        response = self.client.get(reverse("global_tags_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["sorted_tags"].keys()), ["E"])
        self.assertContains(response, "Éducation")

    def test_tag_page_lists_live_tagged_pages(self):
        response = self.client.get(reverse("global_tag", kwargs={"tag": "education"}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["tag"], self.tag)
        self.assertContains(response, "Page étiquetée")
        self.assertNotContains(response, "Brouillon étiqueté")

    def test_unknown_tag_returns_404(self):
        response = self.client.get(reverse("global_tag", kwargs={"tag": "inconnu"}))

        self.assertEqual(response.status_code, 404)


class LanguageSelectorItemCleanTestCase(TestCase):
    def setUp(self):
        self.page = Page.objects.get(slug="home")
        self.config = CmsDsfrConfig.objects.create(site_id=Page.objects.get(slug="home").get_site().pk)

    def item(self, **kwargs):
        return LanguageSelectorItem(site_config=self.config, language_code="en", language_name="English", **kwargs)

    def assert_error_on(self, field, item):
        with self.assertRaises(ValidationError) as context:
            item.clean()
        self.assertEqual(list(context.exception.message_dict.keys()), [field])

    def test_page_or_url_is_required(self):
        self.assert_error_on("page", self.item(link_type="page"))

    def test_page_type_requires_a_page(self):
        self.assert_error_on("page", self.item(link_type="page", external_url="https://example.com"))

    def test_url_type_requires_a_url(self):
        self.assert_error_on("external_url", self.item(link_type="external_url", page=self.page))

    def test_page_type_clears_url(self):
        item = self.item(link_type="page", page=self.page, external_url="https://example.com")

        item.clean()

        self.assertEqual(item.external_url, "")
        self.assertEqual(item.page, self.page)

    def test_url_type_clears_page(self):
        item = self.item(link_type="external_url", page=self.page, external_url="https://example.com")

        item.clean()

        self.assertIsNone(item.page)
        self.assertEqual(item.external_url, "https://example.com")
