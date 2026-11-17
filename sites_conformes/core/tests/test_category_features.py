"""
The category features, from the outside: what a visitor, an editor and an API client get.
The filter logic itself is tested in test_views.
"""

from datetime import timedelta

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from wagtail.models import Locale, Page
from wagtail.test.utils import WagtailPageTestCase
from wagtail.test.utils.form_data import nested_form_data, streamfield

from sites_conformes.blog.models import BlogEntryPage, CategoryEntryPage
from sites_conformes.blog.tests.factories import BlogEntryPageFactory, BlogIndexPageFactory
from sites_conformes.core.models import CatalogIndexPage, Category, ContentPage, Tag
from sites_conformes.events.models import CategoryEventEntryPage, EventEntryPage, EventsIndexPage


def categories(*names, parent=None):
    return [Category.objects.create(name=name, slug=name.lower(), parent=parent) for name in names]


def chip_names(response):
    soup = BeautifulSoup(response.content, "html.parser")
    return [tag.get_text(strip=True) for tag in soup.select(".fr-tags-group .fr-tag:not(p)")]


class CatalogTestCase(WagtailPageTestCase):
    def setUp(self):
        self.home = Page.objects.get(slug="home")
        self.catalog = self.home.add_child(
            instance=CatalogIndexPage(
                title="Catalogue", slug="catalogue", filter_selection=CatalogIndexPage.MULTIPLE_FILTERS
            )
        )
        (self.regions,) = categories("Regions")
        self.bretagne, self.alsace = categories("Bretagne", "Alsace", parent=self.regions)

    def add_entry(self, title, *entry_categories, live=True):
        entry = self.catalog.add_child(instance=ContentPage(title=title, live=live))
        entry.categories.add(*entry_categories)
        entry.save()
        return entry

    def get(self, query=""):
        return self.client.get(f"{self.catalog.url}{query}")

    def titles(self, response):
        return [entry.title for entry in response.context["entries"]]

    def test_an_entry_matching_two_ticked_categories_is_listed_once(self):
        self.add_entry("A", self.bretagne, self.alsace)

        self.assertEqual(self.titles(self.get("?category=bretagne&category=alsace")), ["A"])

    def test_the_cards_show_the_categories_of_the_entry(self):
        self.add_entry("A", self.bretagne)

        soup = BeautifulSoup(self.get().content, "html.parser")

        self.assertEqual([tag.get_text(strip=True) for tag in soup.select(".fr-card p.fr-tag")], ["Bretagne"])

    def test_a_category_only_used_by_a_draft_is_not_offered(self):
        self.add_entry("A", self.bretagne)
        self.add_entry("Brouillon", self.alsace, live=False)

        self.assertEqual(chip_names(self.get()), ["Bretagne"])

    def test_a_draft_is_not_listed_under_its_category(self):
        self.add_entry("A", self.bretagne)
        self.add_entry("Brouillon", self.bretagne, live=False)

        self.assertEqual(self.titles(self.get("?category=bretagne")), ["A"])

    def test_a_category_of_another_locale_is_not_offered(self):
        locale = Locale.objects.create(language_code="en")
        foreign = Category.objects.create(name="Wales", slug="wales", parent=self.regions, locale=locale)
        self.add_entry("A", self.bretagne, foreign)

        self.assertEqual(chip_names(self.get()), ["Bretagne"])

    def test_an_unknown_category_is_ignored(self):
        self.add_entry("A", self.bretagne)

        response = self.get("?category=nope")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.titles(response), ["A"])

    def test_no_filter_is_offered_when_the_page_disables_them(self):
        self.catalog.filter_by_category = False
        self.catalog.save()
        self.add_entry("A", self.bretagne)

        self.assertEqual(chip_names(self.get()), [])

    def test_single_selection_keeps_the_tag_in_the_category_links(self):
        self.catalog.filter_selection = CatalogIndexPage.SINGLE_FILTER
        self.catalog.save()
        entry = self.add_entry("A", self.bretagne)
        tag = Tag.objects.create(name="Eau", slug="eau")
        entry.tags.add(tag)
        entry.save()

        soup = BeautifulSoup(self.get("?tag=eau").content, "html.parser")
        link = next(a for a in soup.select("a.fr-tag") if a.get_text(strip=True) == "Bretagne")

        self.assertIn("tag=eau", link["href"])
        self.assertIn("category=bretagne", link["href"])

    def test_the_checkboxes_reflect_the_selection(self):
        self.add_entry("A", self.bretagne)
        self.add_entry("B", self.alsace)

        soup = BeautifulSoup(self.get("?category=bretagne").content, "html.parser")

        self.assertTrue(soup.select_one("#category-bretagne").has_attr("checked"))
        self.assertFalse(soup.select_one("#category-alsace").has_attr("checked"))
        self.assertEqual(soup.select_one("#category-bretagne")["value"], "bretagne")
        self.assertEqual(soup.select_one("#category-bretagne")["name"], "category")
        self.assertEqual(soup.select_one("#category-bretagne")["data-path"], f"/{self.regions.pk}/{self.bretagne.pk}/")

    def test_the_api_exposes_the_categories_of_a_content_page(self):
        entry = self.add_entry("A", self.bretagne)

        response = self.client.get(reverse("wagtailapi:pages:detail", kwargs={"pk": entry.pk}))

        self.assertEqual([category["slug"] for category in response.json()["categories"]], ["bretagne"])

    def test_copying_a_page_keeps_its_categories(self):
        entry = self.add_entry("A", self.bretagne)

        copy = entry.copy(update_attrs={"title": "B", "slug": "b"})

        self.assertEqual(list(copy.categories.all()), [self.bretagne])

    def test_deleting_a_category_keeps_its_pages(self):
        entry = self.add_entry("A", self.alsace)

        self.alsace.delete()

        self.assertEqual(list(ContentPage.objects.get(pk=entry.pk).categories.all()), [])

    def test_a_draft_keeps_its_categories_until_published(self):
        entry = self.add_entry("A", self.bretagne)

        draft = entry.get_latest_revision_as_object() if entry.latest_revision else entry
        draft.categories.set([self.alsace])
        draft.save_revision()

        self.assertEqual(list(ContentPage.objects.get(pk=entry.pk).categories.all()), [self.bretagne])
        self.assertEqual(list(entry.get_latest_revision_as_object().categories.all()), [self.alsace])

        entry.get_latest_revision().publish()
        self.assertEqual(list(ContentPage.objects.get(pk=entry.pk).categories.all()), [self.alsace])


class EditorTestCase(WagtailPageTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("admin", "admin@example.org", "pass")
        self.client.force_login(self.user)
        self.home = Page.objects.get(slug="home")
        (self.regions,) = categories("Regions")
        self.bretagne, self.alsace = categories("Bretagne", "Alsace", parent=self.regions)

    def form_data(self, **fields):
        form_data = nested_form_data({"hero": streamfield([]), "body": streamfield([]), **fields})
        form_data["categories"] = [self.bretagne.pk]
        return form_data

    def test_an_editor_picks_the_categories_of_a_content_page(self):
        self.assertCanCreate(self.home, ContentPage, self.form_data(title="Page", slug="page"))

        page = ContentPage.objects.get(slug="page")
        self.assertEqual(list(page.categories.all()), [self.bretagne])

    def test_an_editor_picks_the_categories_of_a_blog_post(self):
        index = BlogIndexPageFactory(parent=self.home)

        self.assertCanCreate(
            index, BlogEntryPage, self.form_data(title="Article", slug="article", date="2026-01-01 12:00")
        )

        page = BlogEntryPage.objects.get(slug="article")
        self.assertEqual(list(page.categories.all()), [self.bretagne])


class CategoryGroupsTestMixin:
    """The chosen groups of the blog and the events: both use the same include."""

    link_model = None

    def make_index(self):
        raise NotImplementedError

    def make_entry(self, title):
        raise NotImplementedError

    def link(self, entry, category):
        self.link_model.objects.create(page=entry, category=category)

    def setUp(self):
        self.home = Page.objects.get(slug="home")
        self.index = self.make_index()
        self.regions, self.sectors = categories("Regions", "Secteurs")
        self.bretagne, self.alsace = categories("Bretagne", "Alsace", parent=self.regions)
        (self.btp,) = categories("BTP", parent=self.sectors)
        (self.loose,) = categories("Divers")
        self.entry = self.make_entry("A")
        self.link(self.entry, self.bretagne)
        self.link(self.entry, self.btp)
        self.link(self.entry, self.loose)

    def groups(self, response=None):
        response = response or self.client.get(self.index.url)
        soup = BeautifulSoup(response.content, "html.parser")
        return {
            heading.get_text(strip=True): [
                chip.get_text(strip=True) for chip in heading.find_next("ul").select(".fr-tag")
            ]
            for heading in soup.select("h3.fr-h6")
            if heading.find_next("ul") and heading.find_next("ul").select("a.fr-tag")
        }

    def test_without_groups_every_category_in_use_is_offered(self):
        self.assertEqual(sorted(chip_names(self.client.get(self.index.url))), ["BTP", "Bretagne", "Divers"])

    def test_each_chosen_group_lists_its_subcategories_in_use(self):
        self.index.filter_categories.set([self.regions, self.sectors])
        self.index.save()

        groups = self.groups()

        self.assertEqual(groups["Regions"], ["Bretagne"])
        self.assertEqual(groups["Secteurs"], ["BTP"])

    def test_a_group_without_subcategories_in_use_has_no_heading(self):
        (empty,) = categories("Vide")
        categories("Sous-vide", parent=empty)
        self.index.filter_categories.set([self.regions, empty])
        self.index.save()

        soup = BeautifulSoup(self.client.get(self.index.url).content, "html.parser")

        self.assertNotIn("Vide", [heading.get_text(strip=True) for heading in soup.select("h3.fr-h6")])

    def test_the_selected_category_of_a_group_is_marked(self):
        self.index.filter_categories.set([self.regions])
        self.index.save()

        response = self.client.get(f"{self.index.url}?category=bretagne")
        soup = BeautifulSoup(response.content, "html.parser")
        chip = next(a for a in soup.select("a.fr-tag") if a.get_text(strip=True) == "Bretagne")

        self.assertEqual(chip["aria-pressed"], "true")

    def test_the_preview_shows_the_unsaved_groups(self):
        self.index.filter_categories.set([self.regions])

        response = self.index.make_preview_request()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.groups(response)["Regions"], ["Bretagne"])


class BlogCategoryGroupsTestCase(CategoryGroupsTestMixin, WagtailPageTestCase):
    link_model = CategoryEntryPage

    def make_index(self):
        return BlogIndexPageFactory(parent=self.home)

    def make_entry(self, title):
        return BlogEntryPageFactory(parent=self.index, title=title)


class EventCategoryGroupsTestCase(CategoryGroupsTestMixin, WagtailPageTestCase):
    link_model = CategoryEventEntryPage

    def make_index(self):
        return self.home.add_child(instance=EventsIndexPage(title="Agenda", slug="agenda"))

    def make_entry(self, title):
        end = timezone.now() + timedelta(days=1)
        return self.index.add_child(instance=EventEntryPage(title=title, event_date_start=end, event_date_end=end))
