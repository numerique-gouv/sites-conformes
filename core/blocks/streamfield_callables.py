"""
Callable functions for DynamicStreamField blocks.

These functions return block definitions and can be used with DynamicStreamField
to prevent infinite migrations when adding new blocks.

Instead of directly passing block lists to StreamField, pass these callables.
This allows Django migrations to reference the function instead of the full
block definitions, preventing migration regeneration on every block change.
"""


def get_common_streamfield_blocks():
    """
    Returns the common streamfield blocks for use with DynamicStreamField.

    This function should be used as a callable in DynamicStreamField declarations:
        body = DynamicStreamField(get_common_streamfield_blocks, blank=True, use_json_field=True)

    This prevents infinite migrations by keeping block definitions dynamic.
    The actual block definitions are imported from core.py at runtime, and any
    custom blocks registered via @register_common_block are automatically included.
    """
    from sites_conformes.core.blocks.core import STREAMFIELD_COMMON_BLOCKS
    from sites_conformes.core.registry import get_registered_blocks

    # Start with the core blocks
    blocks = list(STREAMFIELD_COMMON_BLOCKS)

    # Add any custom registered blocks
    blocks.extend(get_registered_blocks())

    return blocks


def get_hero_streamfield_blocks():
    """
    Returns the hero streamfield blocks for use with DynamicStreamField.

    This function should be used as a callable in DynamicStreamField declarations:
        hero = DynamicStreamField(get_hero_streamfield_blocks, blank=True, use_json_field=True, max_num=1)

    This prevents infinite migrations by keeping block definitions dynamic.
    The actual block definitions are imported from core.py at runtime.
    """
    from sites_conformes.core.blocks.core import HERO_STREAMFIELD_BLOCKS

    return HERO_STREAMFIELD_BLOCKS
