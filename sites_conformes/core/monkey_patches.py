"""
Monkey patches applied to third-party libraries at startup.

Applied from ``ContentManagerConfig.ready()``.
"""

from wagtail import blocks
from wagtail_localize.segments.extract import StreamFieldSegmentExtractor


def patch_wagtail_localize_handle_image_block():
    """
    Fix a crash in wagtail-localize when translating a page that contains an
    ``ImageBlock`` nested two struct levels deep, e.g. the ``hero_text_wide_image``
    block (hero -> ``image`` struct -> ``image`` ImageBlock).

    ``handle_struct_block`` only threads the ``raw_value`` one level down
    (``raw_value["value"].get(field_name)``), so a doubly-nested ImageBlock
    receives ``raw_value=None``. ``handle_image_block`` then calls
    ``raw_value.get("type")`` without guarding against ``None``, raising
    ``AttributeError: 'NoneType' object has no attribute 'get'`` (the surrounding
    ``except (KeyError, TypeError)`` does not catch ``AttributeError``). This
    happens regardless of whether an image is actually set.

    Bug still present in wagtail-localize main as of 1.13.1.
    See extract.py::StreamFieldSegmentExtractor.handle_image_block.
    """

    def handle_image_block(self, block, image_block_value, raw_value=None):
        segments = []

        for field_name, block_type in block.child_blocks.items():
            if raw_value and raw_value.get("type") and raw_value.get("value"):
                # for top-level ImageBlock, raw_value has a
                # {"type": "field_name", "value": {"image": X, "alt_text": "", "caption": ""}} format.
                # whereas if the ImageBlock is part of a StructBlock, ListBlock or StreamBlock, we
                # only get the "value" part.
                raw_value = raw_value.get("value")

            try:
                block_raw_value = raw_value.get(field_name)
                block_value = image_block_value if field_name == "image" else block_raw_value
            except (KeyError, TypeError, AttributeError):
                # e.g. raw_value is None (image block with no image), or it is from a chooser
                block_raw_value = None
                block_value = None

            if isinstance(block_type, blocks.CharBlock) and block_value is None:
                block_value = ""

            segments.extend(
                segment.wrap(field_name)
                for segment in self.handle_block(block_type, block_value, raw_value=block_raw_value)
            )

        return segments

    StreamFieldSegmentExtractor.handle_image_block = handle_image_block
