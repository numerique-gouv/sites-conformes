"""
Custom field definitions for sites_conformes content manager.
"""

from functools import cached_property

from wagtail.fields import StreamField


class DynamicStreamField(StreamField):
    """
    A StreamField that prevents Django's migration system from creating new migrations
    when blocks are added or modified.

    This works by:
    1. Accepting a callable function that returns block types
    2. Excluding block type definitions from the migration data via deconstruct()
    3. Lazy evaluation of blocks via @cached_property

    This prevents the infinite migration problem where adding a new block type
    causes Django to detect a model change and create a new migration.

    Usage:
        # In blocks/core.py
        def get_common_blocks():
            return [
                ("paragraph", blocks.RichTextBlock()),
                ("image", ImageBlock()),
                # ... more blocks
            ]

        # In models.py
        from sites_conformes.core.fields import DynamicStreamField
        from sites_conformes.core.blocks.core import get_common_blocks

        class MyPage(Page):
            body = DynamicStreamField(
                get_common_blocks,
                blank=True,
                use_json_field=True
            )

    The callable approach allows you to:
    - Add new blocks without triggering migrations
    - Keep block definitions centralized
    - Still use the full power of StreamField
    - Blocks registered via @register_common_block are automatically included

    Example with mixed approach (static + dynamic blocks):
        body = DynamicStreamField(
            [('paragraph', blocks.RichTextBlock())] + get_extra_blocks(),
            blank=True,
            use_json_field=True
        )
    """

    def __init__(
        self, block_types=None, use_json_field=True, block_lookup=None, **kwargs
    ):
        """
        Initialize the DynamicStreamField.

        Args:
            block_types: Can be either:
                - A list of block tuples: [('name', BlockClass()), ...]
                - A callable that returns such a list: get_common_blocks
                - None (empty list)
            use_json_field: Whether to use JSONField for storage (default: True)
            block_lookup: Optional block lookup dictionary
            **kwargs: Additional field options (blank, null, etc.)
        """
        if block_types is None:
            block_types = []

        # Store the original callable for lazy evaluation
        self._block_types_callable = block_types if callable(block_types) else None

        # For parent __init__, evaluate the callable or use the list
        if callable(block_types):
            block_types = block_types()

        super().__init__(block_types, use_json_field, block_lookup, **kwargs)

    @cached_property
    def stream_block(self):
        """
        Lazy evaluation of the stream_block.

        If block_types was provided as a callable, re-evaluate it here.
        This ensures that blocks registered after model definition
        (e.g., in AppConfig.ready()) are included.
        """
        if self._block_types_callable is not None:
            # Re-create the StreamBlock with fresh blocks from the callable
            from wagtail.blocks import StreamBlock

            block_types = self._block_types_callable()
            return StreamBlock(block_types, required=not self.blank)

        # Fall back to parent implementation
        return super().stream_block

    def deconstruct(self):
        """
        Override deconstruct() to exclude block types from migration data.

        This is the key method that prevents infinite migrations.
        By returning an empty list for block_types in the migration data,
        Django won't detect changes when blocks are added or modified.

        Returns:
            tuple: (name, path, args, kwargs) where args is always empty
        """
        name, path, args, kwargs = super().deconstruct()

        # Return empty args list to prevent block definitions from being
        # included in the migration files
        return name, path, [], kwargs
