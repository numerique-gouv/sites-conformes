import zoneinfo
from datetime import datetime
from itertools import combinations

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.utils.translation import gettext
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from publications.models import Collection, PublicationIndexPage, PublicationPage, Theme
from sites_conformes.blog.models import Organization, Person
from sites_conformes.core.models import Tag

User = get_user_model()

# PublicationIndexPage filter toggles: publications fields default on; blog fields vary.
FILTER_SETTINGS_DEFAULTS = {
    "filter_by_collection": True,
    "filter_by_theme": True,
    "filter_by_tag": True,
    "filter_by_author": False,
    "filter_by_source": False,
}

FILTER_CASES = [
    {
        "name": "collection",
        "setting": "filter_by_collection",
        "heading": gettext("Filter by collection"),
        "visible_label": lambda self: self.collection.name,
        "query_param": lambda self: "collection=agriculture",
        "post_kwargs": lambda self: {"collections": [self.collection]},
        "matching_title": lambda self: self.post_with_collection.title,
        "other_title": lambda self: self.post_with_other_collection.title,
    },
    {
        "name": "theme",
        "setting": "filter_by_theme",
        "heading": gettext("Filter by theme"),
        "visible_label": lambda self: self.theme.name,
        "query_param": lambda self: "theme=climate",
        "post_kwargs": lambda self: {"themes": [self.theme]},
        "matching_title": lambda self: self.post_with_theme.title,
        "other_title": lambda self: self.post_with_other_theme.title,
    },
    {
        "name": "tag",
        "setting": "filter_by_tag",
        "heading": gettext("Filter by tag"),
        "visible_label": lambda self: self.tag.name,
        "query_param": lambda self: "tag=news",
        "post_kwargs": lambda self: {"tags": [self.tag]},
        "matching_title": lambda self: self.post_with_tag.title,
        "other_title": lambda self: self.post_with_other_tag.title,
    },
    {
        "name": "author",
        "setting": "filter_by_author",
        "heading": gettext("Filter by author"),
        "visible_label": lambda self: self.author.name,
        "query_param": lambda self: f"author={self.author.id}",
        "post_kwargs": lambda self: {"authors": [self.author]},
        "matching_title": lambda self: self.post_with_author.title,
        "other_title": lambda self: self.post_with_other_author.title,
    },
    {
        "name": "source",
        "setting": "filter_by_source",
        "heading": gettext("Filter by source"),
        "visible_label": lambda self: self.organization.name,
        "query_param": lambda self: "source=inrae",
        # You can't assign a source to a post directly, so we assign an author associated to the source.
        "post_kwargs": lambda self: {"authors": [self.author]},
        "matching_title": lambda self: self.post_with_author.title,
        "other_title": lambda self: self.post_with_other_author.title,
    },
]

for case in FILTER_CASES:
    case["filter_url"] = lambda self, case=case: (f"{self.index.url}?{case['query_param'](self)}")


def list_settings_in_panel(panels):
    names = []
    for panel in panels:
        if hasattr(panel, "field_name"):
            names.append(panel.field_name)
        if hasattr(panel, "children"):
            names.extend(list_settings_in_panel(panel.children))
    return names


class PublicationIndexPageSettingsTest(WagtailPageTestCase):
    def test_settings_show_filters_panel_includes_all_fields(self):
        field_names = list_settings_in_panel(PublicationIndexPage.settings_panels)
        for field_name in FILTER_SETTINGS_DEFAULTS:
            self.assertIn(field_name, field_names)

    def test_filter_settings_default_values(self):
        home = Page.objects.get(slug="home")
        page = home.add_child(
            instance=PublicationIndexPage(title="Defaults", slug="defaults"),
        )
        for field_name, expected_default in FILTER_SETTINGS_DEFAULTS.items():
            self.assertEqual(getattr(page, field_name), expected_default, field_name)


class PublicationIndexPageFilterTestBase(WagtailPageTestCase):
    def setUp(self):
        self.home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()
        self.paris_tz = zoneinfo.ZoneInfo("Europe/Paris")

        self.index = self.home.add_child(
            instance=PublicationIndexPage(
                title="Publications",
                slug="publications-index",
                owner=self.admin,
            )
        )
        self.index.save_revision().publish()

        locale = self.index.locale
        self.collection = Collection.objects.create(
            name="Agriculture",
            slug="agriculture",
            locale=locale,
        )
        self.other_collection = Collection.objects.create(
            name="Environment",
            slug="environment",
            locale=locale,
        )
        self.theme = Theme.objects.create(name="Climate", slug="climate", locale=locale)
        self.other_theme = Theme.objects.create(name="Health", slug="health", locale=locale)
        self.tag = Tag.objects.create(name="News", slug="news")
        self.other_tag = Tag.objects.create(name="Report", slug="report")
        self.organization = Organization.objects.create(name="INRAE", slug="inrae")
        self.other_organization = Organization.objects.create(name="ANSES", slug="anses")
        self.author = Person.objects.create(
            name="Jane Doe",
            role="Writer",
            organization=self.organization,
        )
        self.other_author = Person.objects.create(
            name="John Smith",
            role="Editor",
            organization=self.other_organization,
        )

        self.post_with_collection = self._create_post(
            "Post Agriculture",
            collections=[self.collection],
        )
        self.post_with_other_collection = self._create_post(
            "Post Environment",
            collections=[self.other_collection],
        )
        self.post_with_theme = self._create_post("Post Climate", themes=[self.theme])
        self.post_with_other_theme = self._create_post("Post Health", themes=[self.other_theme])
        self.post_with_tag = self._create_post("Post News", tags=[self.tag])
        self.post_with_other_tag = self._create_post("Post Report", tags=[self.other_tag])
        self.post_with_author = self._create_post("Post Jane", authors=[self.author])
        self.post_with_other_author = self._create_post("Post John", authors=[self.other_author])

    def _create_post(self, title, collections=None, themes=None, tags=None, authors=None):
        post = PublicationPage(
            title=title,
            date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=self.paris_tz),
            owner=self.admin,
        )
        self.index.add_child(instance=post)
        for collection in collections or []:
            post.collections.add(collection)
        for theme in themes or []:
            post.themes.add(theme)
        for tag in tags or []:
            post.tags.add(tag)
        for author in authors or []:
            post.authors.add(author)
        post.save_revision().publish()
        return post

    def _set_filter_settings(self, **settings):
        for field, value in settings.items():
            setattr(self.index, field, value)
        self.index.save_revision().publish()


class PublicationIndexPageFilterVisibilityTest(PublicationIndexPageFilterTestBase):
    def test_filter_shown_when_enabled(self):
        for case in FILTER_CASES:
            with self.subTest(case["name"]):
                self._set_filter_settings(**{case["setting"]: True})
                response = self.client.get(self.index.url)
                self.assertContains(response, case["heading"])
                self.assertContains(response, case["visible_label"](self))

    def test_filter_hidden_when_disabled(self):
        for case in FILTER_CASES:
            with self.subTest(case["name"]):
                self._set_filter_settings(**{case["setting"]: False})
                response = self.client.get(self.index.url)
                self.assertNotContains(response, case["heading"])


class PublicationIndexPageFilterQueryTest(PublicationIndexPageFilterTestBase):
    def test_filters_posts(self):
        for case in FILTER_CASES:
            with self.subTest(case["name"]):
                response = self.client.get(case["filter_url"](self))
                self.assertContains(response, case["matching_title"](self))
                self.assertNotContains(response, case["other_title"](self))

    def test_url_filter_applies_even_when_filter_disabled_in_settings(self):
        """
        Disabling a filter hides its sidemenu block, but get_context still
        filters posts from the query param.
        """
        for case in FILTER_CASES:
            with self.subTest(case["name"]):
                self._set_filter_settings(**{case["setting"]: False})
                response = self.client.get(case["filter_url"](self))
                self.assertNotContains(response, case["heading"])
                self.assertContains(response, case["matching_title"](self))
                self.assertNotContains(response, case["other_title"](self))

    def test_filters_posts_with_two_query_params(self):
        # Remove the "source" case, because there's interactions with the "author" case that make testing complicated.
        # We'll have less coverage but reliable tests.
        filter_cases = [case for case in FILTER_CASES if case["name"] != "source"]
        for case_a, case_b in combinations(filter_cases, 2):
            with self.subTest(f"{case_a['name']}+{case_b['name']}"):
                title = f"Post with {case_a['name']} and {case_b['name']}"
                kwargs = {**case_a["post_kwargs"](self), **case_b["post_kwargs"](self)}
                matching = self._create_post(title, **kwargs)
                query = f"{self.index.url}?" f"{case_a['query_param'](self)}&{case_b['query_param'](self)}"
                response = self.client.get(query)
                self.assertContains(response, matching.title)
                # Check that posts with only one filter do not show.
                for case in (case_a, case_b):
                    self.assertNotContains(response, case["matching_title"](self))
                    self.assertNotContains(response, case["other_title"](self))


class PublicationIndexPagePostsDisplayTest(PublicationIndexPageFilterTestBase):
    def test_posts_display_collections_and_not_themes(self):
        # Themes are hidden on result cards (publication_index_posts_list.html) because
        # they are too verbose alongside collection tags.
        post = self._create_post(
            "Post with taxonomies",
            collections=[self.collection],
            themes=[self.theme],
        )
        response = self.client.get(self.index.url)  # no filters
        collection_tag = f'<p class="fr-tag">{self.collection.name}</p>'
        theme_tag = f'<p class="fr-tag">{self.theme.name}</p>'
        soup = BeautifulSoup(response.content, "html.parser")
        matching_card = None
        for card in soup.select("div.fr-card"):
            tag_html = "".join(str(tag) for tag in card.select("p.fr-tag"))
            if post.title in card.get_text() and collection_tag in tag_html:
                matching_card = card
                break
        self.assertIsNotNone(
            matching_card,
            "Expected a post card containing the title and the collection tag.",
        )
        self.assertNotIn(theme_tag, "".join(str(tag) for tag in matching_card.select("p.fr-tag")))
