from unittest import skipUnless

from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from wagtail.models import Site, get_page_models
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.blog import models as blog_models
from sites_conformes.blog.models import Category
from sites_conformes.core import SWAPPABLE_MODELS, get_contentpage_model, get_model, models as core_models
from sites_conformes.core.blocks.related_entries import BlogRecentEntriesBlock, EventsRecentEntriesBlock
from sites_conformes.core.models import ContentPage, Tag
from sites_conformes.core.services.accessors import get_or_create_catalog_index_page, get_or_create_content_page
from sites_conformes.events import models as events_models
from sites_conformes.forms import models as forms_models


@skipUnless(apps.is_installed("sites_conformes.testapp"), "requires config.settings_swapped")
class SwappedModelsTestCase(WagtailPageTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.CustomContentPage = get_contentpage_model()
        cls.CatalogIndexPage = get_model("SF_CATALOGINDEXPAGE_MODEL")
        cls.BlogIndexPage = get_model("SF_BLOGINDEXPAGE_MODEL")
        cls.BlogEntryPage = get_model("SF_BLOGENTRYPAGE_MODEL")
        cls.EventsIndexPage = get_model("SF_EVENTSINDEXPAGE_MODEL")
        cls.EventEntryPage = get_model("SF_EVENTENTRYPAGE_MODEL")
        cls.FormPage = get_model("SF_FORMPAGE_MODEL")
        cls.home = Site.objects.get(is_default_site=True).root_page

    def test_settings_swap_the_models(self):
        from sites_conformes.testapp.models import CustomContentPage

        self.assertIs(self.CustomContentPage, CustomContentPage)
        self.assertEqual(ContentPage._meta.swapped, "sites_conformes_testapp.CustomContentPage")

        for setting, shipped in SWAPPABLE_MODELS.items():
            with self.subTest(setting=setting):
                self.assertEqual(get_model(setting)._meta.app_label, "sites_conformes_testapp")
                self.assertTrue(apps.get_model(shipped)._meta.swapped)

    def test_default_models_are_hidden_from_wagtail(self):
        tables = connection.introspection.table_names()
        for setting, shipped in SWAPPABLE_MODELS.items():
            with self.subTest(setting=setting):
                shipped_model = apps.get_model(shipped)
                self.assertNotIn(shipped_model, get_page_models())
                self.assertIn(get_model(setting), get_page_models())
                self.assertNotIn(shipped_model._meta.db_table, tables)

    def test_page_hierarchy_follows_the_swapped_models(self):
        self.assertCanCreateAt(self.CatalogIndexPage, self.CustomContentPage)
        self.assertCanNotCreateAt(self.CatalogIndexPage, ContentPage)
        self.assertAllowedSubpageTypes(self.BlogIndexPage, {self.BlogEntryPage})
        self.assertAllowedParentPageTypes(self.BlogEntryPage, {self.BlogIndexPage})
        self.assertAllowedSubpageTypes(self.EventsIndexPage, {self.EventEntryPage})
        self.assertAllowedParentPageTypes(self.EventEntryPage, {self.EventsIndexPage})

    def test_create_tag_and_render(self):
        page = self.home.add_child(instance=self.CustomContentPage(title="Custom", slug="custom", subtitle="sub"))
        page.tags.add("dsfr")
        page.save()

        self.assertEqual(list(self.CustomContentPage.objects.filter(tags__name="dsfr")), [page])
        self.assertPageIsRenderable(page)

    def test_shipped_through_models_are_not_declared(self):
        self.assertFalse(hasattr(ContentPage, "tags"))
        tables = connection.introspection.table_names()
        for module, names in (
            (core_models, ["TagContentPage"]),
            (blog_models, ["TagEntryPage", "CategoryEntryPage"]),
            (events_models, ["TagEventEntryPage", "CategoryEventEntryPage"]),
            (forms_models, ["FormField"]),
        ):
            for name in names:
                with self.subTest(model=name):
                    self.assertFalse(hasattr(module, name))
                    self.assertNotIn(f"{module.__name__.split('.')[1]}_{name}".lower(), "".join(tables))

    def test_tags_with_usecount_follows_the_swapped_through_model(self):
        page = self.home.add_child(instance=self.CustomContentPage(title="Tagged", slug="tagged", live=True))
        page.tags.add("dsfr")
        page.save()

        self.assertEqual([tag.name for tag in Tag.objects.tags_with_usecount(1)], ["dsfr"])

    def test_catalog_lists_custom_pages(self):
        catalog = get_or_create_catalog_index_page(slug="catalogue", title="Catalogue", body=[])
        self.assertIsInstance(catalog, self.CatalogIndexPage)
        child = catalog.add_child(instance=self.CustomContentPage(title="Entry", slug="entry", live=True))

        self.assertEqual(list(catalog.entries), [child])
        self.assertPageIsRenderable(catalog)

    def test_accessor_creates_the_swapped_model(self):
        page = get_or_create_content_page(slug="via-accessor", title="Via accessor", body=[])
        self.assertIsInstance(page, self.CustomContentPage)

    def test_starter_pages_command_uses_the_swapped_models(self):
        call_command("create_starter_pages", verbosity=0)
        self.assertTrue(self.CustomContentPage.objects.filter(slug="home").exists())

        contact = self.FormPage.objects.get(slug="contact")
        self.assertTrue(contact.form_fields.exists())
        self.assertPageIsRenderable(contact)

    def test_form_page_submission_renders_the_shipped_landing_template(self):
        form_page = self.home.add_child(instance=self.FormPage(title="Contact", slug="contact-form", honeypot=False))
        form_page.form_fields.model.objects.create(page=form_page, label="Name", field_type="singleline")

        response = self.client.post(form_page.url, {"name": "Ada"})

        self.assertTemplateUsed(response, "sites_conformes_forms/form_page_landing.html")
        self.assertEqual(form_page.get_submission_class().objects.filter(page=form_page).count(), 1)

    def test_blog_index_lists_and_filters_custom_entries(self):
        category = Category.objects.create(name="News", slug="news")
        blog = self.home.add_child(instance=self.BlogIndexPage(title="Blog", slug="blog"))
        entry = blog.add_child(instance=self.BlogEntryPage(title="Post", slug="post", subtitle="sub"))
        entry.tags.add("dsfr")
        entry.blog_categories.add(category)
        entry.save()
        blog.add_child(instance=self.BlogEntryPage(title="Other", slug="other"))

        self.assertEqual(blog.posts.count(), 2)
        self.assertEqual(list(blog.get_categories()), [category])
        response = self.client.get(blog.url, {"category": "news"})
        self.assertEqual(list(response.context["posts"]), [entry])
        self.assertTemplateUsed(response, "sites_conformes_blog/blog_index_page.html")
        self.assertPageIsRenderable(entry)

    def test_events_index_lists_custom_entries(self):
        events = self.home.add_child(instance=self.EventsIndexPage(title="Agenda", slug="agenda"))
        tomorrow = timezone.now() + timezone.timedelta(days=1)
        dates = {"event_date_start": tomorrow, "event_date_end": tomorrow}
        entry = events.add_child(instance=self.EventEntryPage(title="Event", slug="event", **dates))
        entry.tags.add("dsfr")
        entry.save()

        self.assertEqual(list(events.posts), [entry])
        self.assertEqual([tag.name for tag in events.get_tags()], ["dsfr"])
        self.assertPageIsRenderable(events)
        self.assertPageIsRenderable(entry)

    def test_recent_entries_blocks_choose_the_swapped_index_pages(self):
        for block, name, model in (
            (BlogRecentEntriesBlock(), "blog", self.BlogIndexPage),
            (EventsRecentEntriesBlock(), "index_page", self.EventsIndexPage),
        ):
            with self.subTest(block=name):
                chooser = block.child_blocks[name]
                self.assertIs(chooser.target_model, model)
                # The migrations keep the shipped model, whatever the settings
                path, _args, kwargs = chooser.deconstruct()
                self.assertEqual(path, "wagtail.blocks.PageChooserBlock")
                self.assertNotIn("testapp", str(kwargs["page_type"]))
