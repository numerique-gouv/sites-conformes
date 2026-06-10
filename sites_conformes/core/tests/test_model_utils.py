from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.checks import check_contentpage_model
from sites_conformes.core.model_utils import get_contentpage_model, get_contentpage_model_string
from sites_conformes.core.models import CatalogIndexPage, ContentPage
from sites_conformes.core.services.accessors import get_or_create_content_page
from sites_conformes.testapp.models import CustomContentPage


class ContentPageModelAccessorsTestCase(WagtailPageTestCase):
    def test_default_model_string(self):
        assert get_contentpage_model_string() == "sites_conformes_core.ContentPage"

    def test_default_model(self):
        assert get_contentpage_model() is ContentPage

    @override_settings(SF_CONTENTPAGE_MODEL="sites_conformes_testapp.CustomContentPage")
    def test_swapped_model(self):
        assert get_contentpage_model_string() == "sites_conformes_testapp.CustomContentPage"
        assert get_contentpage_model() is CustomContentPage

    @override_settings(SF_CONTENTPAGE_MODEL="not_a_dotted_path")
    def test_invalid_model_string_raises(self):
        with self.assertRaises(ImproperlyConfigured):
            get_contentpage_model()

    @override_settings(SF_CONTENTPAGE_MODEL="sites_conformes_core.DoesNotExist")
    def test_uninstalled_model_raises(self):
        with self.assertRaises(ImproperlyConfigured):
            get_contentpage_model()


class ContentPageModelChecksTestCase(WagtailPageTestCase):
    def test_default_model_passes_checks(self):
        assert check_contentpage_model(None) == []

    @override_settings(SF_CONTENTPAGE_MODEL="sites_conformes_core.DoesNotExist")
    def test_uninstalled_model_reported(self):
        errors = check_contentpage_model(None)
        assert [e.id for e in errors] == ["sites_conformes.E001"]

    @override_settings(SF_CONTENTPAGE_MODEL="wagtailcore.Page")
    def test_non_subclass_reported(self):
        errors = check_contentpage_model(None)
        assert [e.id for e in errors] == ["sites_conformes.E002"]


@override_settings(SF_CONTENTPAGE_MODEL="sites_conformes_testapp.CustomContentPage")
class SwappedContentPageTestCase(WagtailPageTestCase):
    """
    Exercise runtime code paths with a custom content page model.

    Note: attributes resolved at class-definition time (such as
    CatalogIndexPage.subpage_types) cannot be changed by override_settings;
    in a real project the setting must be set before startup.
    """

    def setUp(self):
        self.home = Page.objects.get(slug="home")

    def test_accessor_creates_custom_model_page(self):
        page = get_or_create_content_page("custom-page", title="Custom page", body=[])

        assert isinstance(page, CustomContentPage)
        assert page.template == "sites_conformes_core/content_page.html"

    def test_catalog_index_entries_use_custom_model(self):
        catalog = self.home.add_child(instance=CatalogIndexPage(title="Catalog", slug="catalog", body=[]))
        entry = catalog.add_child(instance=CustomContentPage(title="Entry", slug="entry", body=[]))

        assert list(catalog.entries) == [entry]
