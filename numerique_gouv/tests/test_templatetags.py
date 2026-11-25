import uuid
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from numerique_gouv.models import NumeriqueBlogEntryPage, NumeriquePage
from numerique_gouv.templatetags.numerique_filters import first_item_id, is_numerique_blog_entry_page, replace


class ReplaceFilterTestCase(SimpleTestCase):
    def test_replace_with_default_args(self):
        self.assertEqual(replace("1,5"), "1.5")

    def test_replace_with_custom_args(self):
        self.assertEqual(replace("1.5", ".|,"), "1,5")

    def test_replace_converts_decimal(self):
        self.assertEqual(replace(Decimal("2.25"), ".|,"), "2,25")

    def test_replace_without_match_returns_value(self):
        self.assertEqual(replace("abc", "x|y"), "abc")


# Instantiating a Wagtail page queries the default locale, hence TestCase
class IsNumeriqueBlogEntryPageFilterTestCase(TestCase):
    def test_true_for_numerique_blog_entry_page(self):
        self.assertTrue(is_numerique_blog_entry_page(NumeriqueBlogEntryPage(title="Article")))

    def test_false_for_other_values(self):
        self.assertFalse(is_numerique_blog_entry_page(NumeriquePage(title="Page")))
        self.assertFalse(is_numerique_blog_entry_page(None))


class FirstItemIdFilterTestCase(SimpleTestCase):
    def test_empty_items_returns_none(self):
        self.assertIsNone(first_item_id([]))
        self.assertIsNone(first_item_id(None))

    def test_returns_first_id_without_dashes(self):
        item_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        items = [SimpleNamespace(id=item_id), SimpleNamespace(id=uuid.uuid4())]
        self.assertEqual(first_item_id(items), "12345678123456781234567812345678")

    def test_works_with_integer_ids(self):
        self.assertEqual(first_item_id([SimpleNamespace(id=42)]), "42")
