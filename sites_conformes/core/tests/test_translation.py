from wagtail.models import Page
from wagtail.rich_text import RichText
from wagtail.test.utils import WagtailPageTestCase
from wagtail_localize.segments.extract import extract_segments

from sites_conformes.core.models import ContentPage
from sites_conformes.core.utils import import_image


class TranslationImageBlockExtractionTestCase(WagtailPageTestCase):
    """
    Regression test for a 500 when submitting a page for translation
    (POST /cms-admin/localize/submit/page/<id>/).

    wagtail-localize's StreamFieldSegmentExtractor.handle_image_block crashes
    with "'NoneType' object has no attribute 'get'" when an ImageBlock is
    nested two struct levels deep, e.g. the "hero_text_wide_image" block:
        hero_text_wide_image -> image (HeroImageBlockWithRatioWidth) -> image (ImageBlock)
    handle_struct_block only threads the raw_value one level down, so the
    ImageBlock receives raw_value=None and the code calls None.get(...).
    This happens regardless of whether an image is actually set; the page
    renders fine but translation extraction blows up.

    Fixed by sites_conformes.core.monkey_patches (applied in apps.ready()).
    """

    def setUp(self):
        home = Page.objects.get(slug="home")
        image = import_image("sites_conformes/static/artwork/technical-error.svg", "Hero image")

        hero = [
            (
                "hero_text_wide_image",
                {
                    "text_content": {
                        "hero_title": "Sample hero",
                        "hero_subtitle": RichText("<p>Sample subtitle</p>"),
                    },
                    "layout": {"top_margin": 5, "bottom_margin": 5, "background_color": "blue-ecume"},
                    "buttons": [],
                    "image": {
                        "image": {"image": image, "alt_text": "Photo description", "decorative": False},
                        "image_ratio": "fr-ratio-16x9",
                        "image_width": "fr-content-media--sm",
                        "image_positioning": "",
                    },
                },
            )
        ]
        self.content_page = home.add_child(
            instance=ContentPage(
                title="Translation hero image page",
                slug="translation-hero-image",
                hero=hero,
                body=[],
            )
        )
        self.content_page.save()

    def test_extract_segments_with_deeply_nested_image_does_not_crash(self):
        # Without the monkey patch this raises AttributeError:
        # 'NoneType' object has no attribute 'get'
        segments = extract_segments(self.content_page)
        self.assertIsInstance(segments, list)


class TranslationSimpleImageBlockExtractionTestCase(WagtailPageTestCase):
    """
    Make sure the monkey patch does not break extraction for a hero whose ImageBlock is only one
    level deep which never triggered the bug. Here raw_value is a proper dict, so segments must still
    be extracted normally.
    """

    def setUp(self):
        home = Page.objects.get(slug="home")
        image = import_image("sites_conformes/static/artwork/technical-error.svg", "Hero image")

        hero = [
            (
                "hero_text_image",
                {
                    "text_content": {
                        "hero_title": "Sample hero",
                        "hero_subtitle": RichText("<p>Sample subtitle</p>"),
                    },
                    "buttons": [],
                    "image": {"image": image, "alt_text": "Photo description", "decorative": False},
                    "layout": {"top_margin": 5, "bottom_margin": 5, "background_color": "blue-ecume"},
                },
            )
        ]
        self.content_page = home.add_child(
            instance=ContentPage(
                title="Translation simple hero image page",
                slug="translation-simple-hero-image",
                hero=hero,
                body=[],
            )
        )
        self.content_page.save()

    def test_extract_segments_with_single_level_image_still_works(self):
        # The patch must not regress the working case: a one-level-deep
        # ImageBlock must still extract its segments (e.g. the hero title).
        segments = extract_segments(self.content_page)
        self.assertIsInstance(segments, list)
        self.assertTrue(segments, "expected segments to be extracted for a valid hero")
        extracted = " ".join(str(getattr(s, "string", "")) for s in segments)
        self.assertIn("Sample hero", extracted)
