import importlib
import sys

from django.test import SimpleTestCase

from sites_conformes.core.blocks.colophon import COLOPHON_BLOCKS, ContactCardBlock


class DeprecatedBlocksModuleTestCase(SimpleTestCase):
    def test_the_old_path_warns_and_still_exposes_the_blocks(self):
        sys.modules.pop("sites_conformes.blog.blocks", None)

        with self.assertWarnsMessage(DeprecationWarning, "sites_conformes.core.blocks.colophon"):
            module = importlib.import_module("sites_conformes.blog.blocks")

        self.assertIs(module.ContactCardBlock, ContactCardBlock)
        self.assertIs(module.COLOPHON_BLOCKS, COLOPHON_BLOCKS)
