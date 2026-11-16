"""
Base test classes for the multisite features.

Both classes create the fictional demo sites (see ``core/services/demo_sites.py``)
once per test class, without images to keep the tests fast:

- MonositeTestCase: site A alone, with multisite isolation disabled;
- MultisiteTestCase: sites A and B, with multisite isolation enabled.

The created objects are available as ``cls.demo``, ``cls.site_a``, ``cls.site_b``
(None in monosite) and ``cls.users``.
"""

from django.test import override_settings
from wagtail.models import Site
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.services.demo_sites import create_demo_sites


class ClearSiteRootPathsCacheMixin:
    """
    Wagtail caches the root paths of the sites, and rolling back the test transaction does not clear
    this cache: without this mixin, the next tests of the process would see the demo sites.
    """

    def tearDown(self):
        super().tearDown()
        Site.clear_site_root_paths_cache()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        Site.clear_site_root_paths_cache()


class DemoSitesTestCase(ClearSiteRootPathsCacheMixin, WagtailPageTestCase):
    site_keys = ("a", "b")

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.demo = create_demo_sites(site_keys=cls.site_keys, with_media=False)
        cls.site_a = cls.demo.sites.get("a")
        cls.site_b = cls.demo.sites.get("b")
        cls.users = cls.demo.users


@override_settings(SF_MULTISITE_ISOLATION_ENABLED=False)
class MonositeTestCase(DemoSitesTestCase):
    site_keys = ("a",)


@override_settings(SF_MULTISITE_ISOLATION_ENABLED=True)
class MultisiteTestCase(DemoSitesTestCase):
    site_keys = ("a", "b")
