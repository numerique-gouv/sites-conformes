"""
What a blog post or an event with categories does for the projects in production, seen from
the rendered pages and from a v4.3.1 database that went through the migrations.

These tests go through the public paths and names of v4.3.1 on purpose: a change that makes
them fail breaks an existing project, so fix the change rather than the test.
"""

from datetime import timedelta

from bs4 import BeautifulSoup
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.blog.models import BlogEntryPage, Category, CategoryEntryPage, Person
from sites_conformes.blog.tests.factories import BlogEntryPageFactory, BlogIndexPageFactory
from sites_conformes.core.models import ContentPage
from sites_conformes.events.models import CategoryEventEntryPage, EventEntryPage, EventsIndexPage


class CategorizedPagesTestMixin:
    """The same behaviours for blog posts and events: subclasses say how to build them."""

    app_name = ""
    api_key = ""
    index_field = ""
    category_link_model = None

    def make_index(self, parent):
        raise NotImplementedError

    def make_entry(self, parent, title):
        raise NotImplementedError

    def setUp(self):
        super().setUp()
        self.home = Page.objects.get(slug="home")
        self.index = self.make_index(self.home)
        self.category = Category.objects.create(name="Climat", slug="climat")
        self.other_category = Category.objects.create(name="Budget", slug="budget")
        self.author = Person.objects.create(name="Camille Roux")
        self.entry = self.make_entry(self.index, "Vague de chaleur")
        self.entry.authors.add(self.author)
        self.entry.save()
        other_entry = self.make_entry(self.index, "Plan de finances")
        self.category_link_model.objects.create(page=self.entry, category=self.category)
        self.category_link_model.objects.create(page=other_entry, category=self.other_category)

    def get_soup(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return BeautifulSoup(response.content, "html.parser")

    def entry_titles(self, soup):
        return {title.get_text(strip=True) for title in soup.select(".fr-card__title")}

    def recent_entries_page(self, **block_value):
        return self.home.add_child(
            instance=ContentPage(
                title="Actualités",
                slug="actualites",
                body=[
                    (
                        f"{self.app_name}_recent_entries",
                        {
                            "title": "Récents",
                            "heading_tag": "h2",
                            "entries_count": 4,
                            self.index_field: self.index,
                            **block_value,
                        },
                    )
                ],
            )
        )

    def test_the_entry_links_to_the_index_filtered_on_its_category(self):
        soup = self.get_soup(self.entry.url)

        links = {link.get_text(strip=True): link["href"] for link in soup.select("a[href]")}
        self.assertEqual(links["Climat"], f"{self.index.url}?category=climat")
        self.assertNotIn("Budget", links)

    def test_the_entry_shows_its_author_card(self):
        self.assertIn("Camille Roux", self.get_soup(self.entry.url).get_text())

    def test_the_index_shows_the_categories_of_each_entry(self):
        soup = self.get_soup(self.index.url)

        tags = {tag.get_text(strip=True) for tag in soup.select("p.fr-tag")}
        self.assertEqual(tags, {"Climat", "Budget"})

    def test_the_index_filters_on_a_category(self):
        soup = self.get_soup(f"{self.index.url}?category=climat")

        self.assertEqual(self.entry_titles(soup), {"Vague de chaleur"})

    def test_the_recent_entries_block_shows_the_categories(self):
        soup = self.get_soup(self.recent_entries_page().url)

        tags = {tag.get_text(strip=True) for tag in soup.select("p.fr-tag")}
        self.assertEqual(tags, {"Climat", "Budget"})

    def test_the_recent_entries_block_filters_on_a_category(self):
        soup = self.get_soup(self.recent_entries_page(category_filter=self.category).url)

        self.assertEqual(self.entry_titles(soup), {"Vague de chaleur"})

    def test_the_api_keeps_the_categories_under_their_historical_key(self):
        response = self.client.get(reverse("wagtailapi:pages:detail", kwargs={"pk": self.entry.pk}))

        self.assertEqual([category["slug"] for category in response.json()[self.api_key]], ["climat"])


class CategorizedBlogEntryTestCase(CategorizedPagesTestMixin, WagtailPageTestCase):
    app_name = "blog"
    api_key = "blog_categories"
    index_field = "blog"
    category_link_model = CategoryEntryPage

    def make_index(self, parent):
        return BlogIndexPageFactory(parent=parent)

    def make_entry(self, parent, title):
        return BlogEntryPageFactory(parent=parent, title=title)

    def test_the_rss_feed_filters_on_a_category(self):
        response = self.client.get(f"{self.index.url}rss/?category=climat")

        self.assertContains(response, "Vague de chaleur")
        self.assertNotContains(response, "Plan de finances")

    def test_the_categories_page_lists_the_categories_in_use(self):
        soup = self.get_soup(f"{self.index.url}categories/")

        self.assertIn("Climat", soup.get_text())
        self.assertIn("Budget", soup.get_text())


class CategorizedEventTestCase(CategorizedPagesTestMixin, WagtailPageTestCase):
    app_name = "events"
    api_key = "event_categories"
    index_field = "index_page"
    category_link_model = CategoryEventEntryPage

    def make_index(self, parent):
        return parent.add_child(instance=EventsIndexPage(title="Agenda", slug="agenda"))

    def make_entry(self, parent, title):
        # The index only lists the events to come.
        end = timezone.now() + timedelta(days=1)
        return parent.add_child(instance=EventEntryPage(title=title, event_date_start=end, event_date_end=end))


class CategorizedPagesUpgradeTestCase(TransactionTestCase):
    """Run the migrations on the data v4.3.1 left in the database."""

    v4_3_1 = [
        ("sites_conformes_blog", "0067_alter_blogentrypage_body_alter_blogindexpage_body_and_more"),
        ("sites_conformes_core", "0086_alter_catalogindexpage_body_alter_contentpage_body"),
        ("sites_conformes_events", "0039_alter_evententrypage_body_alter_eventsindexpage_body"),
    ]

    def migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def add_page(self, apps, model, title, path, field_values):
        ContentType = apps.get_model("contenttypes", "ContentType")
        content_type, _ = ContentType.objects.get_or_create(
            app_label=model._meta.app_label, model=model._meta.model_name
        )
        page_type, _ = ContentType.objects.get_or_create(app_label="wagtailcore", model="page")
        page = model.objects.create(
            title=title,
            draft_title=title,
            slug=path,
            path=path,
            depth=2,
            url_path=f"/{path}/",
            content_type=content_type,
            locale=field_values.pop("locale"),
            live=True,
        )
        revision = apps.get_model("wagtailcore", "Revision").objects.create(
            content_type=content_type,
            base_content_type=page_type,
            object_id=str(page.pk),
            object_str=title,
            created_at=timezone.now(),
            content={"pk": page.pk, "title": title, "slug": path, "path": path, "depth": 2, **field_values},
        )
        model.objects.filter(pk=page.pk).update(latest_revision=revision)
        return page

    def test_a_page_keeps_its_categories_and_drafts_through_the_upgrade(self):
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(self.migrate, leaves)
        apps = self.migrate(self.v4_3_1)

        locale, _ = apps.get_model("wagtailcore", "Locale").objects.get_or_create(language_code="fr")
        category = apps.get_model("sites_conformes_blog", "Category").objects.create(
            name="Climat", slug="climat", locale=locale
        )
        post = self.add_page(
            apps,
            apps.get_model("sites_conformes_blog", "BlogEntryPage"),
            "Vague de chaleur",
            "90000001",
            {"locale": locale, "blog_categories": [category.pk]},
        )
        apps.get_model("sites_conformes_blog", "CategoryEntryPage").objects.create(page=post, category=category)
        event = self.add_page(
            apps,
            apps.get_model("sites_conformes_events", "EventEntryPage"),
            "Atelier",
            "90000002",
            {"locale": locale, "event_categories": [category.pk]},
        )
        apps.get_model("sites_conformes_events", "CategoryEventEntryPage").objects.create(
            page=event, category=category
        )

        self.migrate(leaves)

        migrated = Category.objects.get(pk=category.pk)
        self.assertEqual((migrated.name, migrated.slug, migrated.locale_id), ("Climat", "climat", locale.pk))
        pages = ((BlogEntryPage, post.pk, "blog_categories"), (EventEntryPage, event.pk, "event_categories"))
        for model, pk, accessor in pages:
            page = model.objects.get(pk=pk)
            draft = page.get_latest_revision_as_object()
            self.assertEqual(list(getattr(page, accessor).all()), [migrated])
            self.assertEqual(list(getattr(draft, accessor).all()), [migrated])
