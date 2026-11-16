from django.test import TestCase
from wagtail.blocks import StructBlockValidationError
from wagtail.documents.models import Document
from wagtail.models import Page

from sites_conformes.blog.tests.factories import PersonFactory
from sites_conformes.core.blocks.basics import VerticalContactCardBlock
from sites_conformes.core.blocks.buttons_links import LinkBlock, LinkWithoutLabelBlock
from sites_conformes.core.blocks.heros import HeroBackgroundImageBlock

# Unit tests for the clean() methods and value classes of blocks


def link_value(**kwargs):
    value = {"link_type": "", "page": None, "document": None, "external_url": "", "anchor": "", "query_string": ""}
    value.update(kwargs)
    # Chooser blocks expect primary keys in their raw value
    for key in ["page", "document"]:
        if value[key] is not None:
            value[key] = value[key].pk
    return LinkWithoutLabelBlock().to_python(value)


class LinkWithoutLabelBlockCleanTestCase(TestCase):
    def setUp(self):
        self.block = LinkWithoutLabelBlock()
        self.page = Page.objects.get(slug="home")

    def assert_error_on(self, field, value):
        with self.assertRaises(StructBlockValidationError) as context:
            self.block.clean(value)
        self.assertEqual(list(context.exception.block_errors.keys()), [field])

    def test_missing_target_raises_on_selected_field(self):
        self.assert_error_on("page", link_value(link_type="page"))
        self.assert_error_on("external_url", link_value(link_type="external_url"))
        self.assert_error_on("document", link_value(link_type="document"))

    def test_link_type_is_inferred_when_missing(self):
        cleaned = self.block.clean(link_value(external_url="https://example.com"))

        self.assertEqual(cleaned["link_type"], "external_url")
        self.assertEqual(cleaned["external_url"], "https://example.com")

    def test_other_targets_are_cleared(self):
        cleaned = self.block.clean(
            link_value(
                link_type="page",
                page=self.page,
                external_url="https://example.com",
                anchor="section",
                query_string="?a=1",
            )
        )

        self.assertEqual(cleaned["page"], self.page)
        self.assertFalse(cleaned["external_url"])
        self.assertIsNone(cleaned["document"])
        # Anchor and query string are only kept for links to a page
        self.assertEqual(cleaned["anchor"], "section")
        self.assertEqual(cleaned["query_string"], "?a=1")

    def test_external_url_drops_anchor_and_query_string(self):
        cleaned = self.block.clean(
            link_value(link_type="external_url", external_url="https://example.com", anchor="x", query_string="?a=1")
        )

        self.assertEqual(cleaned["anchor"], "")
        self.assertEqual(cleaned["query_string"], "")

    def test_anchor_link_drops_query_string(self):
        cleaned = self.block.clean(link_value(link_type="anchor", anchor="section", query_string="?a=1"))

        self.assertEqual(cleaned["anchor"], "section")
        self.assertEqual(cleaned["query_string"], "")


class LinkStructValueTestCase(TestCase):
    def setUp(self):
        self.page = Page.objects.get(slug="home")

    def test_external_url(self):
        value = link_value(external_url="https://example.com")

        self.assertEqual(value.url(), "https://example.com")

    def test_page_with_anchor_and_query_string(self):
        value = link_value(page=self.page, anchor="section", query_string="?a=1")

        self.assertEqual(value.url(), f"{self.page.url}#section?a=1")

    def test_document(self):
        document = Document.objects.create(title="Rapport", file="documents/rapport.pdf")
        value = link_value(document=document)

        self.assertEqual(value.url(), document.url)

    def test_label_defaults_to_target_title(self):
        block = LinkBlock()
        document = Document.objects.create(title="Rapport", file="documents/rapport.pdf")

        self.assertEqual(block.to_python({"text": "Mon lien", "page": self.page.pk}).label(), "Mon lien")
        self.assertEqual(block.to_python({"text": "", "page": self.page.pk}).label(), self.page.title)
        self.assertEqual(block.to_python({"text": "", "document": document.pk}).label(), "Rapport")
        self.assertEqual(block.to_python({"text": "", "external_url": "https://example.com"}).label(), "")


class HeroBackgroundImageBlockCleanTestCase(TestCase):
    def setUp(self):
        self.block = HeroBackgroundImageBlock()

    def value(self, **kwargs):
        value = self.block.get_default()
        # The default example buttons are partial values completed by the admin form
        value["buttons"] = self.block.child_blocks["buttons"].to_python([])
        for key, item in kwargs.items():
            value[key] = item
        return value

    def assert_error_on(self, field, value):
        with self.assertRaises(StructBlockValidationError) as context:
            self.block.clean(value)
        self.assertEqual(list(context.exception.block_errors.keys()), [field])

    def test_color_background_requires_a_color(self):
        self.assert_error_on("background_color", self.value(background_color_or_image="color", background_color=None))

    def test_image_background_requires_an_image(self):
        self.assert_error_on("image", self.value(background_color_or_image="image", image=None))

    def test_missing_type_without_values_defaults_to_image(self):
        self.assert_error_on("image", self.value(background_color_or_image="", background_color=None, image=None))

    def test_missing_type_is_inferred_from_color(self):
        value = self.value(background_color_or_image="", background_color="blue-france")

        cleaned = self.block.clean(value)

        self.assertEqual(cleaned["background_color_or_image"], "color")
        self.assertEqual(cleaned["background_color"], "blue-france")

    def test_image_background_clears_the_color(self):
        value = self.value(background_color_or_image="image", background_color="blue-france")

        cleaned = self.block.clean(value)

        self.assertEqual(cleaned["background_color_or_image"], "image")
        self.assertFalse(cleaned["background_color"])


class VerticalContactCardStructValueTestCase(TestCase):
    def setUp(self):
        self.block = VerticalContactCardBlock()
        self.person = PersonFactory(name="Jeanne Martin", role="Développeuse")

    def card(self, **kwargs):
        value = {"contact": None, "name": "", "role": "", "organization": "", "image": None, "tags": []}
        value.update(kwargs)
        return self.block.to_python(value)

    def test_display_falls_back_to_contact(self):
        display = self.card(contact=self.person.pk).display()

        self.assertEqual(display["name"], "Jeanne Martin")
        self.assertEqual(display["role"], "Développeuse")
        self.assertEqual(display["organization"], self.person.organization.name)

    def test_display_values_override_contact(self):
        display = self.card(
            contact=self.person.pk, name="Autre nom", role="Autre rôle", organization="Autre"
        ).display()

        self.assertEqual(display["name"], "Autre nom")
        self.assertEqual(display["role"], "Autre rôle")
        self.assertEqual(display["organization"], "Autre")

    def test_enlarge_link_requires_a_link(self):
        self.assertFalse(self.card(link={"external_url": ""}).enlarge_link())

    def test_enlarge_link_with_plain_tags(self):
        tag = {
            "type": "tag",
            "value": {"label": "Tag", "link": {"page": None, "document": None, "external_url": ""}},
        }
        card = self.card(link={"external_url": "https://example.com"}, tags=[tag])

        self.assertTrue(card.enlarge_link())

    def test_no_enlarge_link_with_linked_tags(self):
        tag = {
            "type": "tag",
            "value": {"label": "Tag", "link": {"page": None, "document": None, "external_url": "https://example.org"}},
        }
        card = self.card(link={"external_url": "https://example.com"}, tags=[tag])

        self.assertFalse(card.enlarge_link())
