from django.test import SimpleTestCase

from sites_conformes.core import abstract


class DeprecatedBasePageAliasTestCase(SimpleTestCase):
    def test_old_name_warns_and_returns_new_class(self):
        with self.assertWarns(DeprecationWarning):
            old_class = abstract.SitesFacilesBasePage
        self.assertIs(old_class, abstract.SitesConformesBasePage)

    def test_unknown_name_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            abstract.DoesNotExist  # noqa: B018
