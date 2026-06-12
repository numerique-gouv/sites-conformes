"""
Register publications StreamField blocks on Sites Conformes page types. It's hacky.

Sites Conformes copies ``STREAMFIELD_COMMON_BLOCKS`` into each page model at class
definition time. Host projects add blocks at startup without editing
``sites_conformes`` (see ``register_sites_conformes_blocks``):

- ``publication_recent_entries`` on each page ``StreamField`` that already allows
  ``blog_recent_entries`` (typically ``body``, sometimes ``header_cta_buttons``, …).
- ``publication_recent_entries`` on nested ``CommonStreamBlock`` instances inside
  multicolumns, tabs, item grids, etc.

Nested block instances are created at import time and keep their own ``child_blocks``
copy, so class-level ``base_blocks`` patching alone is not enough: we also walk each
registered stream definition and patch every ``StreamBlock`` instance in the tree.

HACK to avoid migrations: registration is skipped during ``makemigrations`` /
``squashmigrations`` so ``sites_conformes`` schema files are not touched.
"""

import sys

from django.apps import apps
from wagtail import blocks
from wagtail.blocks import StreamBlock
from wagtail.fields import StreamField

from publications.blocks.recent_entries import (
    PUBLICATION_RECENT_ENTRIES_BLOCK,
    PublicationRecentEntriesBlock,
)
from sites_conformes.core.abstract import SitesFacilesBasePage

_MIGRATION_AUTHORING_COMMANDS = frozenset({"makemigrations", "squashmigrations"})


def _is_migration_authoring_command() -> bool:
    return len(sys.argv) > 1 and sys.argv[1] in _MIGRATION_AUTHORING_COMMANDS


BLOG_RECENT_ENTRIES_BLOCK = "blog_recent_entries"


def _make_block(group) -> PublicationRecentEntriesBlock:
    block = PublicationRecentEntriesBlock(group=group)
    block.set_name(PUBLICATION_RECENT_ENTRIES_BLOCK)
    return block


def _add_publication_recent_entries_to_blocks(blocks_mapping: dict) -> bool:
    """Add ``publication_recent_entries`` next to ``blog_recent_entries`` in a block mapping."""
    if BLOG_RECENT_ENTRIES_BLOCK not in blocks_mapping:
        return False
    if PUBLICATION_RECENT_ENTRIES_BLOCK in blocks_mapping:
        return False
    blog_block = blocks_mapping[BLOG_RECENT_ENTRIES_BLOCK]
    blocks_mapping[PUBLICATION_RECENT_ENTRIES_BLOCK] = _make_block(blog_block.meta.group)
    return True


def _walk_and_patch_block_tree(block) -> None:
    """Patch every ``StreamBlock`` in the tree that allows ``blog_recent_entries``."""
    if isinstance(block, StreamBlock):
        _add_publication_recent_entries_to_blocks(block.child_blocks)
        for child in block.child_blocks.values():
            _walk_and_patch_block_tree(child)
        return

    if isinstance(block, blocks.StructBlock):
        for child in block.child_blocks.values():
            _walk_and_patch_block_tree(child)
        return

    if isinstance(block, blocks.ListBlock):
        _walk_and_patch_block_tree(block.child_block)


def _add_publication_recent_entries_to_stream_field(field) -> bool:
    """Register on a model ``StreamField`` whose block list already includes ``blog_recent_entries``."""
    if not hasattr(field, "stream_block"):
        return False

    current_block = field.stream_block
    _walk_and_patch_block_tree(current_block)
    return BLOG_RECENT_ENTRIES_BLOCK in current_block.child_blocks


def _register_publication_recent_entries_on_common_stream_blocks() -> None:
    """Patch ``CommonStreamBlock`` class definitions for newly created instances."""
    from sites_conformes.core.blocks.layout import CommonStreamBlock

    def all_subclasses(cls):
        for subclass in cls.__subclasses__():
            yield subclass
            yield from all_subclasses(subclass)

    for block_cls in (CommonStreamBlock, *all_subclasses(CommonStreamBlock)):
        if BLOG_RECENT_ENTRIES_BLOCK not in block_cls.base_blocks:
            continue
        _add_publication_recent_entries_to_blocks(block_cls.base_blocks)


def register_sites_conformes_blocks():
    """Add ``publication_recent_entries`` wherever ``blog_recent_entries`` is already allowed."""
    if _is_migration_authoring_command():
        return

    _register_publication_recent_entries_on_common_stream_blocks()

    for model in apps.get_models():
        if model._meta.abstract or not issubclass(model, SitesFacilesBasePage):
            continue
        for field in model._meta.get_fields():
            if not isinstance(field, StreamField):
                continue
            _add_publication_recent_entries_to_stream_field(field)
