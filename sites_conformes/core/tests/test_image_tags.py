from bs4 import BeautifulSoup
from django.template import Context, Template
from django.test import TestCase
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file


class DynamicSpecPictureTagTestCase(TestCase):
    def setUp(self):
        self.image = get_image_model().objects.create(title="Photo", file=get_test_image_file(size=(400, 300)))

    def render(self, template, **context):
        html = Template("{% load sites_conformes_images %}" + template).render(
            Context({"image": self.image, **context})
        )
        return BeautifulSoup(html, "html.parser")

    def test_spec_variable_is_applied_before_the_literal_specs(self):
        img = self.render('{% picture image spec=spec format-webp class="photo" %}', spec="fill-100x50").img

        self.assertTrue(img["src"].endswith(".webp"))
        self.assertEqual((img["width"], img["height"]), ("100", "50"))
        self.assertEqual(img["class"], ["photo"])
        self.assertNotIn("spec", img.attrs)

    def test_without_spec_it_is_wagtails_picture_tag(self):
        img = self.render("{% picture image width-200 format-webp %}").img

        self.assertTrue(img["src"].endswith(".webp"))
        self.assertEqual(img["width"], "200")

    def test_renders_nothing_without_an_image(self):
        self.assertEqual(
            str(self.render("{% picture image spec=spec format-webp %}", image=None, spec="width-100")), ""
        )
