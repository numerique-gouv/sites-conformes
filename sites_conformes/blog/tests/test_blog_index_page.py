"""Blog index page tests.

The tests are structured to allow easier future transition from single Categories to multiple Taxonomies.
The test classes are structured so that page types with multiple taxonomies can reuse them by subclassing.
Taxonomy-specific elements are overridden in subclasses (see publications tests in https://github.com/betagouv/agreste).
"""

from itertools import combinations

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.utils.translation import gettext
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.blog.models import BlogIndexPage
from sites_conformes.blog.tests.factories import (
    BlogEntryPageFactory,
    BlogIndexPageFactory,
    CategoryFactory,
    OrganizationFactory,
    PersonFactory,
    TagFactory,
)

User = get_user_model()


def get_post_titles_in_response(response) -> list[str]:
    return [
        link.get_text(strip=True)
        for link in BeautifulSoup(response.content, "html.parser").select("#posts-list .fr-card__title a")
    ]


FILTER_SETTINGS_DEFAULTS = {
    "filter_by_category": True,
    "filter_by_tag": True,
    "filter_by_author": False,
    "filter_by_source": False,
}

FILTER_CASES = [
    {
        "name": "category",
        "relation": "blog_categories",
    },
    {
        "name": "tag",
        "relation": "tags",
    },
    # Author and source are not in these cases because they behave a bit differently,
    # so we test them separately.
]


class BlogIndexPageFilterTestBase(WagtailPageTestCase):
    # Classes and factories exposed for overriding in subclasses,
    # in particular for projects implementing multiple taxonomies.
    # We can probably remove it when we have cleaner code for multiple taxonomies.
    index_page_class = BlogIndexPage
    index_page_factory = BlogIndexPageFactory
    entry_page_factory = BlogEntryPageFactory
    filter_cases = FILTER_CASES

    def setUp(self):
        self.home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()

        self.index = self.index_page_factory(parent=self.home, owner=self.admin)

        self.setup_filter_fixtures()
        self.setup_taxonomy_filter_fixtures()

    def setup_filter_fixtures(self):
        self.tag = TagFactory()
        self.other_tag = TagFactory()
        self.organization = OrganizationFactory()
        self.other_organization = OrganizationFactory()
        self.author = PersonFactory(organization=self.organization)
        self.other_author = PersonFactory(organization=self.other_organization)

        self.post_with_tag = self.entry_page_factory(parent=self.index, owner=self.admin, tags=[self.tag])
        self.post_with_other_tag = self.entry_page_factory(parent=self.index, owner=self.admin, tags=[self.other_tag])
        self.post_with_author = self.entry_page_factory(parent=self.index, owner=self.admin, authors=[self.author])
        self.post_with_other_author = self.entry_page_factory(
            parent=self.index, owner=self.admin, authors=[self.other_author]
        )

    def setup_taxonomy_filter_fixtures(self):
        locale = self.index.locale
        self.category = CategoryFactory(locale=locale)
        self.other_category = CategoryFactory(locale=locale)

        self.post_with_category = self.entry_page_factory(
            parent=self.index,
            owner=self.admin,
            blog_categories=[self.category],
        )
        self.post_with_other_category = self.entry_page_factory(
            parent=self.index,
            owner=self.admin,
            blog_categories=[self.other_category],
        )

    def _set_filter_settings(self, **settings):
        for field, value in settings.items():
            setattr(self.index, field, value)
        self.index.save_revision().publish()


class BlogIndexPageSettingsTest(BlogIndexPageFilterTestBase):
    """Test the "Show filters" panel in the page settings, and that it shows/hides filters in
    the left sidebar of the page."""

    filter_settings_defaults = FILTER_SETTINGS_DEFAULTS

    def test_settings_show_filters_panel_includes_all_fields(self):
        def list_settings_in_panel(panels):
            names = []
            for panel in panels:
                if hasattr(panel, "field_name"):
                    names.append(panel.field_name)
                if hasattr(panel, "children"):
                    names.extend(list_settings_in_panel(panel.children))
            return names

        filter_settings_found = list_settings_in_panel(self.index_page_class.settings_panels)
        for filter_setting_expected in self.filter_settings_defaults:
            self.assertIn(filter_setting_expected, filter_settings_found)

    def test_filter_settings_default_values(self):
        index_page = self.index_page_factory(parent=self.home, title="Defaults", slug="defaults", publish=False)
        for filter_setting, expected_default in self.filter_settings_defaults.items():
            self.assertEqual(getattr(index_page, filter_setting), expected_default, filter_setting)

    def test_filter_shown_when_enabled(self):
        """Test that the filter is shown in the left sidebar in the rendered page
        when it is enabled in the page settings."""
        for case in self.filter_cases:
            filter_name = case["name"]
            taxonomy = getattr(self, filter_name)
            setting_field = f"filter_by_{filter_name}"
            sidebar_heading = gettext(f"Filter by {filter_name}")

            with self.subTest(filter_name):
                self._set_filter_settings(**{setting_field: True})
                response = self.client.get(self.index.url)
                sidebar = BeautifulSoup(response.content, "html.parser").select_one("nav.fr-sidemenu")
                self.assertIsNotNone(sidebar)
                self.assertIsNotNone(sidebar.find("h3", string=sidebar_heading))
                sidebar_labels = [tag.get_text(strip=True) for tag in sidebar.select("a.fr-tag")]
                self.assertIn(taxonomy.name, sidebar_labels)

        with self.subTest("author"):
            self._set_filter_settings(filter_by_author=True)
            response = self.client.get(self.index.url)
            sidebar = BeautifulSoup(response.content, "html.parser").select_one("nav.fr-sidemenu")
            self.assertIsNotNone(sidebar)
            self.assertIsNotNone(sidebar.find("h3", string=gettext("Filter by author")))
            sidebar_labels = [tag.get_text(strip=True) for tag in sidebar.select("a.fr-tag")]
            self.assertIn(self.author.name, sidebar_labels)

        with self.subTest("source"):
            self._set_filter_settings(filter_by_source=True)
            response = self.client.get(self.index.url)
            sidebar = BeautifulSoup(response.content, "html.parser").select_one("nav.fr-sidemenu")
            self.assertIsNotNone(sidebar)
            self.assertIsNotNone(sidebar.find("h3", string=gettext("Filter by source")))
            sidebar_labels = [tag.get_text(strip=True) for tag in sidebar.select("a.fr-tag")]
            self.assertIn(self.organization.name, sidebar_labels)

    def test_filter_hidden_when_disabled(self):
        """Test that the filter is hidden in the left sidebar in the rendered page
        when it is disabled in the page settings."""
        for case in self.filter_cases:
            filter_name = case["name"]
            setting_field = f"filter_by_{filter_name}"
            sidebar_heading = gettext(f"Filter by {filter_name}")

            with self.subTest(filter_name):
                self._set_filter_settings(**{setting_field: False})
                response = self.client.get(self.index.url)
                self.assertNotContains(response, sidebar_heading)

        with self.subTest("author"):
            self._set_filter_settings(filter_by_author=False)
            response = self.client.get(self.index.url)
            self.assertNotContains(response, gettext("Filter by author"))

        with self.subTest("source"):
            self._set_filter_settings(filter_by_source=False)
            response = self.client.get(self.index.url)
            self.assertNotContains(response, gettext("Filter by source"))


class BlogIndexPageFilterQueryTest(BlogIndexPageFilterTestBase):
    """Test the filtering of the posts on the index page."""

    def test_filters_posts(self):
        for case in self.filter_cases:
            filter_name = case["name"]
            taxonomy = getattr(self, filter_name)
            filtered_url = f"{self.index.url}?{filter_name}={taxonomy.slug}"
            matching_post_title = getattr(self, f"post_with_{filter_name}").title
            other_post_title = getattr(self, f"post_with_other_{filter_name}").title

            with self.subTest(filter_name):
                response = self.client.get(filtered_url)
                post_titles = get_post_titles_in_response(response)
                self.assertIn(matching_post_title, post_titles)
                self.assertNotIn(other_post_title, post_titles)

    def test_filters_posts_by_author(self):
        filter_url = f"{self.index.url}?author={self.author.id}"
        response = self.client.get(filter_url)
        post_titles = get_post_titles_in_response(response)
        self.assertIn(self.post_with_author.title, post_titles)
        self.assertNotIn(self.post_with_other_author.title, post_titles)

    def test_filters_posts_by_source(self):
        # Posts are filtered by the author's organization, not a direct source field.
        filter_url = f"{self.index.url}?source={self.organization.slug}"
        response = self.client.get(filter_url)
        post_titles = get_post_titles_in_response(response)
        self.assertIn(self.post_with_author.title, post_titles)
        self.assertNotIn(self.post_with_other_author.title, post_titles)

    def test_url_filter_applies_even_when_filter_disabled_in_settings(self):
        """
        Disabling a filter hides its sidemenu block, but passing it in the URL still filters the posts.
        """
        for case in self.filter_cases:
            filter_name = case["name"]
            taxonomy = getattr(self, filter_name)
            setting_field = f"filter_by_{filter_name}"
            sidebar_heading = gettext(f"Filter by {filter_name}")
            filter_url = f"{self.index.url}?{filter_name}={taxonomy.slug}"
            matching_post_title = getattr(self, f"post_with_{filter_name}").title
            other_post_title = getattr(self, f"post_with_other_{filter_name}").title

            with self.subTest(filter_name):
                self._set_filter_settings(**{setting_field: False})
                response = self.client.get(filter_url)
                self.assertNotContains(response, sidebar_heading)
                post_titles = get_post_titles_in_response(response)
                self.assertIn(matching_post_title, post_titles)
                self.assertNotIn(other_post_title, post_titles)

    def test_url_author_filter_applies_even_when_filter_disabled_in_settings(self):
        filter_url = f"{self.index.url}?author={self.author.id}"
        self._set_filter_settings(filter_by_author=False)
        response = self.client.get(filter_url)
        self.assertNotContains(response, gettext("Filter by author"))
        post_titles = get_post_titles_in_response(response)
        self.assertIn(self.post_with_author.title, post_titles)
        self.assertNotIn(self.post_with_other_author.title, post_titles)

    def test_url_source_filter_applies_even_when_filter_disabled_in_settings(self):
        filter_url = f"{self.index.url}?source={self.organization.slug}"
        self._set_filter_settings(filter_by_source=False)
        response = self.client.get(filter_url)
        self.assertNotContains(response, gettext("Filter by source"))
        post_titles = get_post_titles_in_response(response)
        self.assertIn(self.post_with_author.title, post_titles)
        self.assertNotIn(self.post_with_other_author.title, post_titles)

    def test_filters_posts_with_two_query_params(self):
        """Tests pairs of filters, to check that they interact correctly."""
        for case_a, case_b in combinations(self.filter_cases, 2):
            filter_a = case_a["name"]
            filter_b = case_b["name"]
            query = (
                f"{self.index.url}?"
                f"{filter_a}={getattr(self, filter_a).slug}&"
                f"{filter_b}={getattr(self, filter_b).slug}"
            )
            post_kwargs = {
                case_a["relation"]: [getattr(self, filter_a)],
                case_b["relation"]: [getattr(self, filter_b)],
            }

            with self.subTest(f"{filter_a}+{filter_b}"):
                matching = self.entry_page_factory(parent=self.index, owner=self.admin, **post_kwargs)
                response = self.client.get(query)
                post_titles = get_post_titles_in_response(response)
                self.assertIn(matching.title, post_titles)
                for case in (case_a, case_b):
                    case_name = case["name"]
                    self.assertNotIn(getattr(self, f"post_with_{case_name}").title, post_titles)
                    self.assertNotIn(getattr(self, f"post_with_other_{case_name}").title, post_titles)


class BlogIndexPagePostsTest(BlogIndexPageFilterTestBase):
    """Test the display of the post list on the index page."""

    def test_posts_display_taxonomies_on_cards(self):
        post = self.entry_page_factory(
            parent=self.index,
            owner=self.admin,
            blog_categories=[self.category],
        )
        response = self.client.get(self.index.url)  # no filters
        category_tag = f'<p class="fr-tag">{self.category.name}</p>'
        soup = BeautifulSoup(response.content, "html.parser")
        matching_card = None
        for card in soup.select("div.fr-card"):
            tag_html = "".join(str(tag) for tag in card.select("p.fr-tag"))
            if post.title in card.get_text() and category_tag in tag_html:
                matching_card = card
                break
        self.assertIsNotNone(
            matching_card,
            "Expected a post card containing the title and the category tag.",
        )
