from django.test import SimpleTestCase

from sites_conformes.forms import baseform, models


class DeprecatedBaseFormAliasTestCase(SimpleTestCase):
    def test_old_name_warns_and_returns_new_class(self):
        with self.assertWarns(DeprecationWarning):
            old_class = baseform.SitesFacilesBaseForm
        self.assertIs(old_class, baseform.SitesConformesBaseForm)

    def test_unknown_name_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            baseform.DoesNotExist  # noqa: B018


class DeprecatedFormModelsAliasesTestCase(SimpleTestCase):
    def test_old_names_warn_and_return_new_classes(self):
        for old_name, new_class in (
            ("SitesFacilesCustomForm", models.SitesConformesCustomForm),
            ("SitesFacilesFormBuilder", models.SitesConformesFormBuilder),
        ):
            with self.subTest(old_name=old_name), self.assertWarns(DeprecationWarning):
                self.assertIs(getattr(models, old_name), new_class)

    def test_unknown_name_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            models.DoesNotExist  # noqa: B018
