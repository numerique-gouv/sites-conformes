"""
Register publications StreamField blocks on Sites Conformes page types.

Sites Conformes copies ``STREAMFIELD_COMMON_BLOCKS`` into each page model at class
definition time. Host projects add blocks by rebuilding each model's ``body``
``StreamBlock`` at startup (see ``register_sites_conformes_blocks``).

HACK to avoid migrations : register the block only if not in a migration
authoring command. Otherwise it would create migrations in sites_conformes,
which we can't maintain.
"""

import sys

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.utils.translation import gettext_lazy as _
from wagtail.blocks import StreamBlock

from publications.blocks.recent_entries import (
    PUBLICATION_RECENT_ENTRIES_BLOCK,
    PublicationRecentEntriesBlock,
)
from sites_conformes.core.abstract import SitesFacilesBasePage

_publication_recent_entries_block = PublicationRecentEntriesBlock(
    label=_("Publication recent entries"),
    group=_("4. Website structure"),
)

_MIGRATION_AUTHORING_COMMANDS = frozenset({"makemigrations", "squashmigrations"})


def _is_migration_authoring_command() -> bool:
    return len(sys.argv) > 1 and sys.argv[1] in _MIGRATION_AUTHORING_COMMANDS


def register_sites_conformes_blocks():
    """Add publications blocks to Sites Conformes page types with a ``body`` StreamField."""
    if _is_migration_authoring_command():
        return

    for model in apps.get_models():
        if model._meta.abstract or not issubclass(model, SitesFacilesBasePage):
            continue
        try:
            field = model._meta.get_field("body")
        except FieldDoesNotExist:
            continue
        if not hasattr(field, "stream_block"):
            continue

        current_block = field.stream_block
        if PUBLICATION_RECENT_ENTRIES_BLOCK in current_block.child_blocks:
            continue

        child_blocks = list(current_block.child_blocks.items()) + [
            (PUBLICATION_RECENT_ENTRIES_BLOCK, _publication_recent_entries_block),
        ]
        new_stream_block = StreamBlock(child_blocks)
        new_stream_block.set_meta_options(field.block_opts)
        field.stream_block = new_stream_block
