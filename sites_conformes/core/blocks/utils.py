from wagtail import blocks
from wagtail.images.blocks import ImageBlock, ImageChooserBlock
from wagtail.rich_text import RichText
from wagtail.snippets.blocks import SnippetChooserBlock

try:
    from wagtailmarkdown.blocks import MarkdownBlock
except ImportError:
    MarkdownBlock = None


def block_to_sample_dict(block):
    # Returns a minimal valid Python value for the given Wagtail block instance.
    # Chooser blocks return None so the caller can substitute a real object when needed.

    # Chooser blocks
    if isinstance(block, ImageChooserBlock):
        return None

    if isinstance(block, (blocks.PageChooserBlock, SnippetChooserBlock)):
        return None

    try:
        from wagtail.documents.blocks import DocumentChooserBlock

        if isinstance(block, DocumentChooserBlock):
            return None
    except ImportError:
        pass

    # ImageBlock is a StructBlock with image / alt_text / decorative fields
    if isinstance(block, ImageBlock):
        return {"image": None, "alt_text": "", "decorative": True}

    if isinstance(block, blocks.StaticBlock):
        return None

    # Text blocks
    if isinstance(block, blocks.RichTextBlock):
        return RichText("<p>Sample</p>")

    if isinstance(block, (blocks.CharBlock, blocks.TextBlock)):
        return "Sample text"

    if isinstance(block, blocks.URLBlock):
        return "https://example.com"

    if isinstance(block, blocks.EmailBlock):
        return "sample@example.com"

    if isinstance(block, blocks.RawHTMLBlock):
        return ""

    if MarkdownBlock is not None and isinstance(block, MarkdownBlock):
        return "## Sample\n\nText"

    # Numeric and boolean blocks
    if isinstance(block, blocks.IntegerBlock):
        min_val = getattr(block, "min_value", None)
        return min_val if min_val is not None else 0

    if isinstance(block, blocks.FloatBlock):
        return 0.0

    if isinstance(block, blocks.DecimalBlock):
        return 0

    if isinstance(block, blocks.BooleanBlock):
        return False

    # ChoiceBlock: return the first valid choice value
    # choices can be a flat list of (value, label) or a grouped list of (group, [(value, label), ...])
    if isinstance(block, blocks.ChoiceBlock):
        choices = block.field.choices
        for choice in choices:
            if isinstance(choice[1], (list, tuple)):
                for sub_value, _sub_label in choice[1]:
                    return sub_value
            else:
                return choice[0]
        return ""

    # StructBlock: recurse into child blocks
    if isinstance(block, blocks.StructBlock):
        result = {}
        for name, child_block in block.child_blocks.items():
            result[name] = block_to_sample_dict(child_block)
        return result

    # StreamBlock: one entry is enough to satisfy required/min_num constraints
    if isinstance(block, blocks.StreamBlock):
        entries = []
        for name, child_block in block.child_blocks.items():
            required = getattr(child_block, "required", True)
            min_num = getattr(child_block, "min_num", None)
            if required or (min_num is not None and min_num > 0):
                entries.append((name, block_to_sample_dict(child_block)))
                break
        return entries

    if isinstance(block, blocks.ListBlock):
        return []

    # Date blocks
    if isinstance(block, blocks.DateBlock):
        from datetime import date

        return date(2024, 1, 1)

    if isinstance(block, blocks.DateTimeBlock):
        from datetime import datetime

        return datetime(2024, 1, 1, 0, 0)

    if isinstance(block, blocks.TimeBlock):
        from datetime import time

        return time(0, 0)

    return ""


def stream_entry(block_name: str, block_instance) -> tuple:
    # Convenience wrapper: returns (block_name, block_to_sample_dict(block_instance)).
    return (block_name, block_to_sample_dict(block_instance))
