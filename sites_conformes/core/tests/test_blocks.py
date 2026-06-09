from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from wagtail.models import Page
from wagtail.rich_text import RichText
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.blog.models import BlogEntryPage, BlogIndexPage
from sites_conformes.core.models import ContentPage
from sites_conformes.core.utils import import_image
from sites_conformes.events.models import EventEntryPage, EventsIndexPage

# Tests for blocks that have a value_class

User = get_user_model()


class TypedTableBlockTestCase(WagtailPageTestCase):
    def setUp(self) -> None:
        home = Page.objects.get(slug="home")

        body = [
            {
                "type": "table",
                "value": {
                    "columns": [
                        {"type": "text", "heading": "Name"},
                        {"type": "text", "heading": "Comment"},
                    ],
                    "rows": [
                        {
                            "values": [
                                '<p data-block-key="ab12c">Line 1</p>',
                                '<p data-block-key="def34g">Example text with <b>formating</b>.</p>',
                            ]
                        },
                        {
                            "values": [
                                '<p data-block-key="hij56k">Line 2</p>',
                                '<p data-block-key="lmn78o">Example other text with <b>formating</b>.</p>',
                            ]
                        },
                    ],
                    "caption": "Example table",
                },
            }
        ]

        self.content_page = home.add_child(
            instance=ContentPage(title="Sample table page", slug="content-page", body=body)
        )
        self.content_page.save()

    def test_page_with_table_is_renderable(self):
        self.assertPageIsRenderable(self.content_page)

    def test_page_with_table_has_content(self):
        response = self.client.get(self.content_page.url)

        self.assertInHTML(
            """<tr>
                <th scope="col">Name</th>
                <th scope="col">Comment</th>
        </tr>""",
            response.content.decode(),
        )

    def test_thead_row_is_not_shown_if_col_headings_are_empty(self):
        body = [
            {
                "type": "table",
                "value": {
                    "columns": [
                        {"type": "text", "heading": ""},
                        {"type": "text", "heading": ""},
                    ],
                    "rows": [
                        {
                            "values": [
                                '<p data-block-key="ab12c">Line 1</p>',
                                '<p data-block-key="def34g">Example text with <b>formating</b>.</p>',
                            ]
                        },
                        {
                            "values": [
                                '<p data-block-key="hij56k">Line 2</p>',
                                '<p data-block-key="lmn78o">Example other text with <b>formating</b>.</p>',
                            ]
                        },
                    ],
                    "caption": "Example table",
                },
            }
        ]

        self.content_page.body = body
        self.content_page.save()

        response = self.client.get(self.content_page.url)

        self.assertNotContains(
            response,
            "thead",
        )


class HorizontalCardBlockTestCase(WagtailPageTestCase):
    # Logic *should* be the same for a vertical card, but inside of a multiple columns block.
    def setUp(self):
        home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()

        body = [
            (
                "card",
                {
                    "title": "Sample card",
                    "description": RichText('<p data-block-key="test">This is a sample card.</p>'),
                },
            )
        ]
        self.content_page = home.add_child(
            instance=ContentPage(title="Sample cards page", slug="content-page", owner=self.admin, body=body)
        )
        self.content_page.save()

    def test_basic_card_is_renderable(self):
        self.assertPageIsRenderable(self.content_page)

    def test_basic_card_has_structure_and_content(self):
        url = self.content_page.url
        response = self.client.get(url)

        self.assertContains(
            response,
            "fr-card fr-card--horizontal",
        )
        self.assertInHTML("""<h3 class="fr-card__title">Sample card</h3>""", response.content.decode())
        self.assertInHTML(
            """<p class="fr-card__desc" data-block-key="test">This is a sample card.</p>""", response.content.decode()
        )

    def test_card_with_no_link_does_not_have_enlarge_class(self):
        url = self.content_page.url
        response = self.client.get(url)

        # The page header and footer have the class on the bloc-marque,
        # The card with no link should not, so count should be 2
        self.assertContains(response, "fr-enlarge-link", count=2)

    def test_card_with_main_link(self):
        body = [
            (
                "card",
                {
                    "title": "Sample card",
                    "description": "This is a sample card.",
                    "link": {
                        "link_type": "external_url",
                        "external_url": "https://www.info.gouv.fr",
                        "page": None,
                        "document": None,
                        "anchor": "",
                    },
                },
            )
        ]
        self.content_page.body = body
        self.content_page.save()

        url = self.content_page.url
        response = self.client.get(url)

        # Count = 3 (page header and footer, card)
        self.assertContains(response, "fr-enlarge-link", count=3)

        self.assertInHTML(
            """<a href="https://www.info.gouv.fr" target="_blank" rel="noopener noreferrer">Sample card
            <span class="fr-sr-only">Ouvre une nouvelle fenêtre</span></a>""",
            response.content.decode(),
        )

    def test_card_with_cta_links(self):
        body = [
            (
                "card",
                {
                    "title": "Sample card",
                    "description": "This is a sample card.",
                    "link": {
                        "link_type": "external_url",
                        "external_url": "https://www.info.gouv.fr",
                        "page": None,
                        "document": None,
                        "anchor": "",
                    },
                    "call_to_action": [
                        {
                            "type": "links",
                            "value": [
                                {
                                    "type": "link",
                                    "value": {
                                        "page": None,
                                        "text": "Lien externe",
                                        "external_url": "https://numerique.gouv.fr",
                                    },
                                }
                            ],
                        }
                    ],
                },
            )
        ]
        self.content_page.body = body
        self.content_page.save()

        url = self.content_page.url
        response = self.client.get(url)

        # Count = 3 (page header and footer, but not the card as it has several links)
        self.assertContains(response, "fr-enlarge-link", count=2)

        self.assertInHTML(
            """<a href="https://www.info.gouv.fr" target="_blank" rel="noopener noreferrer">Sample card
            <span class="fr-sr-only">Ouvre une nouvelle fenêtre</span></a>""",
            response.content.decode(),
        )

        self.assertInHTML(
            """<ul class="fr-links-group">
                <li>
                    <a href="https://numerique.gouv.fr" target="_blank" rel="noopener external">Lien externe</a>
                </li>
            </ul>""",
            response.content.decode(),
        )

    def test_card_with_cta_buttons(self):
        body = [
            (
                "card",
                {
                    "title": "Sample card",
                    "description": "This is a sample card.",
                    "link": {
                        "link_type": "external_url",
                        "external_url": "https://www.info.gouv.fr",
                        "page": None,
                        "document": None,
                        "anchor": "",
                    },
                    "call_to_action": [
                        {
                            "type": "buttons",
                            "value": [
                                {
                                    "type": "button",
                                    "value": {
                                        "page": None,
                                        "text": "Label",
                                        "button_type": "fr-btn fr-btn--secondary",
                                        "external_url": "https://numerique.gouv.fr",
                                    },
                                },
                            ],
                        }
                    ],
                },
            )
        ]
        self.content_page.body = body
        self.content_page.save()

        url = self.content_page.url
        response = self.client.get(url)

        # Count = 3 (page header and footer, but not the card as it has several links)
        self.assertContains(response, "fr-enlarge-link", count=2)

        self.assertInHTML(
            """<a href="https://www.info.gouv.fr" target="_blank" rel="noopener noreferrer">Sample card
            <span class="fr-sr-only">Ouvre une nouvelle fenêtre</span></a>""",
            response.content.decode(),
        )

        self.assertInHTML(
            """<div class="fr-btns-group fr-btns-group--inline-lg">
                  <a class="fr-btn fr-btn--secondary"
                  href="https://numerique.gouv.fr"
                  target="_blank"
                  rel="noopener external">Label <span class="fr-sr-only">Ouvre une nouvelle fenêtre</span></a>
            </div>""",
            response.content.decode(),
        )

    def test_card_with_basic_top_tag(self):
        body = [
            (
                "card",
                {
                    "title": "Sample card",
                    "description": "This is a sample card.",
                    "link": {
                        "link_type": "external_url",
                        "external_url": "https://www.info.gouv.fr",
                        "page": None,
                        "document": None,
                        "anchor": "",
                    },
                    "top_detail_badges_tags": [
                        {
                            "type": "tags",
                            "value": [
                                {
                                    "type": "tag",
                                    "value": {
                                        "link": {"page": None, "external_url": ""},
                                        "color": "purple-glycine",
                                        "label": "Tag 1",
                                        "is_small": False,
                                        "icon_class": "fr-icon-community-fill",
                                    },
                                },
                            ],
                        }
                    ],
                },
            )
        ]
        self.content_page.body = body
        self.content_page.save()

        url = self.content_page.url
        response = self.client.get(url)

        # Count = 3 (page header and footer, card)
        self.assertContains(response, "fr-enlarge-link", count=3)

        self.assertInHTML(
            """<a href="https://www.info.gouv.fr" target="_blank" rel="noopener noreferrer">Sample card
            <span class="fr-sr-only">Ouvre une nouvelle fenêtre</span></a>""",
            response.content.decode(),
        )

        self.assertInHTML(
            """<ul class="fr-tags-group">
                <li>
                    <p class="fr-tag fr-tag--purple-glycine fr-icon-community-fill fr-tag--icon-left">Tag 1</p>
                </li>
            </ul>""",
            response.content.decode(),
        )

    def test_card_with_linked_top_tag(self):
        body = [
            (
                "card",
                {
                    "title": "Sample card",
                    "description": "This is a sample card.",
                    "link": {
                        "link_type": "external_url",
                        "external_url": "https://www.info.gouv.fr",
                        "page": None,
                        "document": None,
                        "anchor": "",
                    },
                    "top_detail_badges_tags": [
                        {
                            "type": "tags",
                            "value": [
                                {
                                    "type": "tag",
                                    "value": {
                                        "link": {"page": None, "external_url": "https://numerique.gouv.fr"},
                                        "color": "purple-glycine",
                                        "label": "Tag 1",
                                        "is_small": False,
                                        "icon_class": "fr-icon-community-fill",
                                    },
                                },
                            ],
                        }
                    ],
                },
            )
        ]
        self.content_page.body = body
        self.content_page.save()

        url = self.content_page.url
        response = self.client.get(url)

        # Count = 3 (page header and footer, but not the card as it has several links)
        self.assertContains(response, "fr-enlarge-link", count=2)

        self.assertInHTML(
            """<a href="https://www.info.gouv.fr" target="_blank" rel="noopener noreferrer">Sample card
            <span class="fr-sr-only">Ouvre une nouvelle fenêtre</span></a>""",
            response.content.decode(),
        )

        self.assertInHTML(
            """<ul class="fr-tags-group">
                <li>
                    <a href="https://numerique.gouv.fr"
                    class="fr-tag fr-tag--purple-glycine fr-icon-community-fill fr-tag--icon-left">Tag 1</a>
                </li>
            </ul>""",
            response.content.decode(),
        )


class TileBlockTestCase(WagtailPageTestCase):
    def setUp(self):
        home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()

        body = [
            (
                "tile",
                {
                    "title": "Sample tile",
                    "description": RichText('<p data-block-key="test">This is a sample tile.</p>'),
                },
            )
        ]
        self.content_page = home.add_child(
            instance=ContentPage(title="Sample tiles page", slug="content-page", owner=self.admin, body=body)
        )
        self.content_page.save()

    def test_basic_tile_is_renderable(self):
        self.assertPageIsRenderable(self.content_page)

    def test_basic_tile_has_no_header_div(self):
        url = self.content_page.url

        response = self.client.get(url)

        self.assertNotContains(response, "fr-tile__header")

    def test_tile_with_image_has_div(self):
        image_file = "sites_conformes/static/artwork/technical-error.svg"
        image = import_image(image_file, "Sample image")

        body = [
            (
                "tile",
                {
                    "title": "Sample tile",
                    "description": RichText('<p data-block-key="test">This is a sample tile.</p>'),
                    "image": image,
                },
            )
        ]

        self.content_page.body = body
        self.content_page.save()

        url = self.content_page.url

        response = self.client.get(url)

        self.assertContains(response, "fr-tile__header")

    @override_settings(SF_SCHEME_DEPENDENT_SVGS=True)
    def test_tile_manages_svg_image_if_setting_allows(self):
        image_file = "sites_conformes/static/artwork/technical-error.svg"
        image = import_image(image_file, "Sample image")

        body = [
            (
                "tile",
                {
                    "title": "Sample tile",
                    "description": RichText('<p data-block-key="test">This is a sample tile.</p>'),
                    "image": image,
                },
            )
        ]

        self.content_page.body = body
        self.content_page.save()

        url = self.content_page.url

        response = self.client.get(url)

        self.assertContains(response, "fr-tile__pictogram")


class BlogRecentEntriesBlockTestCase(WagtailPageTestCase):
    def setUp(self):
        home_page = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()

        lorem_raw = "<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>"
        lorem_body = []
        lorem_body.append(("paragraph", RichText(lorem_raw)))

        blog_index = home_page.add_child(
            instance=BlogIndexPage(title="Actualités", body=lorem_body, slug="actualités", show_in_menus=True)
        )

        _blog_entry = blog_index.add_child(instance=BlogEntryPage(title="Article", body=lorem_body, slug="article"))

        body = [
            (
                "blog_recent_entries",
                {"title": "Actus", "heading_tag": "h2", "blog": blog_index, "entries_count": 4},
            )
        ]
        self.content_page = home_page.add_child(
            instance=ContentPage(title="Sample page", slug="content-page", owner=self.admin, body=body)
        )
        self.content_page.save()

    def test_blog_recent_entries_is_renderable(self):
        self.assertPageIsRenderable(self.content_page)


class EventsRecentEntriesBlockTestCase(WagtailPageTestCase):
    def setUp(self):
        home_page = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()

        lorem_raw = "<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>"
        lorem_body = []
        lorem_body.append(("paragraph", RichText(lorem_raw)))

        events_index = home_page.add_child(
            instance=EventsIndexPage(title="Agenda", body=lorem_body, slug="agenda", show_in_menus=True)
        )

        _event_entry = events_index.add_child(
            instance=EventEntryPage(title="Formation", body=lorem_body, slug="formation")
        )

        body = [
            (
                "events_recent_entries",
                {"title": "Actus", "heading_tag": "h2", "index_page": events_index, "entries_count": 4},
            )
        ]
        self.content_page = home_page.add_child(
            instance=ContentPage(title="Sample page", slug="content-page", owner=self.admin, body=body)
        )
        self.content_page.save()

    def test_events_recent_entries_is_renderable(self):
        self.assertPageIsRenderable(self.content_page)


class HeroBackgroundImageBlockTestCase(WagtailPageTestCase):
    """
    Reproduces the bug:
      1. Create a "page de contenu" with an "En-tête avec arrière-plan" (hero with background).
      2. Publish with an image background.
      3. Edit the page and switch "Image ou couleur en arrière-plan" to a color.
      4. Re-save / publish.
      5. The published page renders a 500.
    """

    def setUp(self):
        home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("hero-bg-test", "test@test.test", "pass")

        image_file = "sites_conformes/static/artwork/technical-error.svg"
        self.image = import_image(image_file, "Hero background image")
        # The hero block's inner image uses ImageBlockWithDefault with this title;
        # its presence is what triggers the bug when an empty image dict is loaded
        # back from the StreamField JSON.
        self.default_image = import_image(image_file, "Banner Sites Faciles Dimitri Iakymuk Unsplash")

        hero_with_image = [
            (
                "hero_text_background_image",
                {
                    "text_content": {
                        "hero_title": "Sample hero",
                        "hero_subtitle": RichText("<p>Sample subtitle</p>"),
                        "position": "",
                    },
                    "buttons": [],
                    "background_color_or_image": "image",
                    "image": {
                        "image": {"image": self.image, "alt_text": "Image de fond", "decorative": False},
                        "image_positioning": "",
                        "image_mask": "",
                    },
                    "background_color": None,
                },
            )
        ]

        self.content_page = home.add_child(
            instance=ContentPage(
                title="Hero background bug page",
                slug="hero-background-bug",
                owner=self.admin,
                hero=hero_with_image,
                body=[],
            )
        )
        self.content_page.save()

    def test_hero_with_image_background_is_renderable(self):
        """Baseline: the page renders correctly with an image background."""
        self.assertPageIsRenderable(self.content_page)

    def test_hero_switched_from_image_to_color_is_renderable(self):
        """
        Bug reproduction: switching the background from image to color after
        an initial publish must not break rendering.
        """
        hero_with_color = [
            (
                "hero_text_background_image",
                {
                    "text_content": {
                        "hero_title": "Sample hero",
                        "hero_subtitle": RichText("<p>Sample subtitle</p>"),
                        "position": "",
                    },
                    "buttons": [],
                    "background_color_or_image": "color",
                    "image": {},
                    "background_color": "blue-france",
                },
            )
        ]
        self.content_page.hero = hero_with_color
        self.content_page.save()

        self.assertPageIsRenderable(self.content_page)

        response = self.client.get(self.content_page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "background-color: var(--background-alt-blue-france)")

    def test_hero_switched_to_color_admin_edit_does_not_500(self):
        """
        After switching the background to a color, re-opening the admin edit page
        must not crash. Regression test for:
          TypeError: Field 'id' expected a number but got
          {'image': <Image: …>, 'alt_text': '', 'decorative': True}.
        The crash happens inside ImageBlock.get_form_state because
        ImageBlockWithDefault.get_default() returns a raw dict that is then
        forwarded to the image chooser widget as if it were an Image instance.
        """
        self.content_page.hero = [
            (
                "hero_text_background_image",
                {
                    "text_content": {
                        "hero_title": "Sample hero",
                        "hero_subtitle": RichText("<p>Sample subtitle</p>"),
                        "position": "",
                    },
                    "buttons": [],
                    "background_color_or_image": "color",
                    "image": {},
                    "background_color": "blue-france",
                },
            )
        ]
        self.content_page.save()

        self.client.force_login(self.admin)
        edit_url = reverse("wagtailadmin_pages:edit", args=[self.content_page.id])
        response = self.client.get(edit_url)
        self.assertEqual(response.status_code, 200)
