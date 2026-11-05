import importlib
import sys

from django.test import SimpleTestCase, TestCase

from sites_conformes.blog.models import BlogEntryPage
from sites_conformes.core.blocks.colophon import COLOPHON_BLOCKS, ContactCardBlock
from sites_conformes.events.models import EventEntryPage


class DeprecatedBlocksModuleTestCase(SimpleTestCase):
    def test_the_old_path_warns_and_still_exposes_the_blocks(self):
        sys.modules.pop("sites_conformes.blog.blocks", None)

        with self.assertWarnsMessage(DeprecationWarning, "sites_conformes.core.blocks.colophon"):
            module = importlib.import_module("sites_conformes.blog.blocks")

        self.assertIs(module.ContactCardBlock, ContactCardBlock)
        self.assertIs(module.COLOPHON_BLOCKS, COLOPHON_BLOCKS)


class DeprecatedCategoryAccessorsTestCase(TestCase):
    def test_the_old_names_warn_and_still_read_the_categories(self):
        for page, accessor in ((BlogEntryPage(), "blog_categories"), (EventEntryPage(), "event_categories")):
            with self.subTest(accessor), self.assertWarnsMessage(DeprecationWarning, f"{accessor} is deprecated"):
                self.assertIs(getattr(page, accessor).model, page.categories.model)
