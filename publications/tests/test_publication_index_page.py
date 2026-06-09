import zoneinfo
from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
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
        "filter_url": lambda self: f"{self.index.url}?collection=agriculture",
        "matching_post": "post_with_collection",
        "other_post": "post_with_other_collection",
    },
    {
        "name": "theme",
        "setting": "filter_by_theme",
        "heading": gettext("Filter by theme"),
        "visible_label": lambda self: self.theme.name,
        "filter_url": lambda self: f"{self.index.url}?theme=climate",
        "matching_post": "post_with_theme",
        "other_post": "post_with_other_theme",
    },
    {
        "name": "tag",
        "setting": "filter_by_tag",
        "heading": gettext("Filter by tag"),
        "visible_label": lambda self: self.tag.name,
        "filter_url": lambda self: f"{self.index.url}?tag=news",
        "matching_post": "post_with_tag",
        "other_post": "post_with_other_tag",
    },
    {
        "name": "author",
        "setting": "filter_by_author",
        "heading": gettext("Filter by author"),
        "visible_label": lambda self: self.author.name,
        "filter_url": lambda self: f"{self.index.url}?author={self.author.id}",
        "matching_post": "post_with_author",
        "other_post": "post_with_other_author",
    },
    {
        "name": "source",
        "setting": "filter_by_source",
        "heading": gettext("Filter by source"),
        "visible_label": lambda self: self.organization.name,
        "filter_url": lambda self: f"{self.index.url}?source=inrae",
        "matching_post": "post_with_author",
        "other_post": "post_with_other_author",
    },
]


def settings_panel_field_names(panels):
    """
    List model field names from a Wagtail panel tree (including nested panels).

    Wagtail page settings are grouped in panels (FieldPanel, MultiFieldPanel, …).
    A MultiFieldPanel like "Show filters" wraps several FieldPanels; this helper
    walks the tree and collects every ``field_name``.

    Example::

        names = settings_panel_field_names(PublicationIndexPage.settings_panels)
        # ["filter_by_collection", "filter_by_theme", "filter_by_tag", ...]
        assert "filter_by_collection" in names
    """
    names = []
    for panel in panels:
        if hasattr(panel, "field_name"):
            names.append(panel.field_name)
        if hasattr(panel, "children"):
            names.extend(settings_panel_field_names(panel.children))
    return names


class PublicationIndexPageSettingsTest(SimpleTestCase):
    def test_settings_show_filters_panel_includes_all_fields(self):
        field_names = settings_panel_field_names(PublicationIndexPage.settings_panels)
        for field_name in FILTER_SETTINGS_DEFAULTS:
            self.assertIn(field_name, field_names)

    def test_filter_settings_default_values(self):
        for field_name, expected_default in FILTER_SETTINGS_DEFAULTS.items():
            field = PublicationIndexPage._meta.get_field(field_name)
            self.assertEqual(field.default, expected_default, field_name)

        page = PublicationIndexPage(title="Defaults", slug="defaults")
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
                self.assertContains(response, getattr(self, case["matching_post"]).title)
                self.assertNotContains(response, getattr(self, case["other_post"]).title)
