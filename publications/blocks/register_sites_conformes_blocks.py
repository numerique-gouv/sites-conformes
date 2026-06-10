"""
Register publications StreamField blocks on Sites Conformes page types.

Sites Conformes copies ``STREAMFIELD_COMMON_BLOCKS`` into each page model at class
definition time. Host projects add blocks by rebuilding each model's ``body``
``StreamBlock`` at startup (see ``register_sites_conformes_blocks``).
"""

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.utils.translation import gettext_lazy as _
from wagtail.blocks import StreamBlock
from wagtail.models import Page

from publications.blocks.recent_entries import (
    PUBLICATION_RECENT_ENTRIES_BLOCK,
    PublicationRecentEntriesBlock,
)

_publication_recent_entries_block = PublicationRecentEntriesBlock(
    label=_("Publication recent entries"),
    group=_("4. Website structure"),
)


def register_sites_conformes_blocks():
    """Add publications blocks to every page model that has a ``body`` StreamField."""
    for model in apps.get_models():
        if not issubclass(model, Page):
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
