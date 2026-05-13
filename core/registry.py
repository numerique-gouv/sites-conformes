"""
Block registry system for sites_conformes.

This module provides a decorator-based system for registering custom blocks
that will be automatically added to STREAMFIELD_COMMON_BLOCKS.

This allows developers to extend the available blocks without modifying
the core block definitions, which is essential for preventing migration issues.

Usage:
    from sites_conformes.core.registry import register_common_block
    from wagtail import blocks

    @register_common_block(label="My Custom Block", group="Custom Blocks")
    class MyCustomBlock(blocks.StructBlock):
        title = blocks.CharBlock()
        content = blocks.RichTextBlock()

        class Meta:
            icon = "placeholder"
            template = "my_app/blocks/my_custom_block.html"
"""

from typing import Any, Callable, Optional, Type

from wagtail import blocks


class BlockRegistry:
    """
    Registry for custom StreamField blocks.

    Maintains a collection of registered blocks that can be dynamically
    added to STREAMFIELD_COMMON_BLOCKS at runtime.
    """

    def __init__(self):
        self._blocks: list[tuple[str, blocks.Block, dict[str, Any]]] = []

    def register(
        self,
        block_class: Type[blocks.Block],
        name: Optional[str] = None,
        label: Optional[str] = None,
        group: Optional[str] = None,
        **kwargs,
    ) -> Type[blocks.Block]:
        """
        Register a block class to be included in STREAMFIELD_COMMON_BLOCKS.

        Args:
            block_class: The block class to register
            name: Optional block name (defaults to snake_case of class name)
            label: Optional label for the block in the admin UI
            group: Optional group name for organizing blocks in the admin
            **kwargs: Additional arguments to pass to the block constructor

        Returns:
            The original block class (unmodified)
        """
        # Generate name from class name if not provided
        if name is None:
            # Convert CamelCase to snake_case
            name = "".join(
                ["_" + c.lower() if c.isupper() else c for c in block_class.__name__]
            ).lstrip("_")

        # Store block info
        block_info = {"label": label, "group": group}
        block_info.update(kwargs)

        self._blocks.append((name, block_class, block_info))

        return block_class

    def get_blocks(self) -> list[tuple[str, blocks.Block]]:
        """
        Get all registered blocks as (name, block_instance) tuples.

        Returns:
            List of tuples containing block name and instantiated block
        """
        result = []
        for name, block_class, block_info in self._blocks:
            # Filter out None values from block_info
            clean_info = {k: v for k, v in block_info.items() if v is not None}
            # Instantiate the block with the provided arguments
            block_instance = block_class(**clean_info)
            result.append((name, block_instance))
        return result

    def clear(self):
        """Clear all registered blocks (useful for testing)."""
        self._blocks.clear()


# Global registry instance
_registry = BlockRegistry()


def register_common_block(
    block_class: Optional[Type[blocks.Block]] = None,
    *,
    name: Optional[str] = None,
    label: Optional[str] = None,
    group: Optional[str] = None,
    **kwargs,
) -> Callable:
    """
    Decorator to register a custom block for STREAMFIELD_COMMON_BLOCKS.

    Can be used with or without arguments:

        @register_common_block
        class MyBlock(blocks.StructBlock):
            ...

        @register_common_block(label="My Block", group="Custom")
        class MyBlock(blocks.StructBlock):
            ...

    Args:
        block_class: The block class (when used without parentheses)
        name: Optional custom name for the block (defaults to snake_case class name)
        label: Optional label for the admin UI
        group: Optional group for organizing blocks in the admin
        **kwargs: Additional keyword arguments passed to block constructor

    Returns:
        The decorator function or the decorated class

    Examples:
        >>> @register_common_block(label="Custom Widget", group="Widgets")
        ... class CustomWidget(blocks.StructBlock):
        ...     title = blocks.CharBlock()

        >>> @register_common_block
        ... class SimpleBlock(blocks.CharBlock):
        ...     pass
    """

    def decorator(cls: Type[blocks.Block]) -> Type[blocks.Block]:
        return _registry.register(cls, name=name, label=label, group=group, **kwargs)

    # Handle both @register_common_block and @register_common_block(...)
    if block_class is not None:
        # Called without parentheses: @register_common_block
        return decorator(block_class)
    else:
        # Called with parentheses: @register_common_block(...)
        return decorator


def get_registered_blocks() -> list[tuple[str, blocks.Block]]:
    """
    Get all registered custom blocks.

    Returns:
        List of (name, block_instance) tuples for all registered blocks

    This function is called by get_common_streamfield_blocks() to include
    custom blocks in the StreamField configuration.
    """
    return _registry.get_blocks()


def clear_registry():
    """
    Clear all registered blocks.

    This is primarily useful for testing to ensure a clean state
    between test runs.
    """
    _registry.clear()
