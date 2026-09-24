import logging
import re

from bs4 import BeautifulSoup
from django.http import HttpRequest
from wagtail.blocks import CharBlock, ListBlock, RichTextBlock, StreamBlock, StructBlock, TextBlock
from wagtailmarkdown.blocks import MarkdownBlock

logger = logging.getLogger(__name__)

REMOVABLE_BLOCK_NAMES = frozenset(
    {
        "separator",
        "html",
        "iframe",
    }
)
DO_NOT_RENDER_TEMPLATES = frozenset(
    {
        "blog_recent_entries",
        "events_recent_entries",
        "publication_recent_entries",
    }
)
SEARCH_DESCRIPTION_MAX_CHARS = 300
_HIDDEN_CONTENT_SELECTOR = ".fr-sr-only, .visually-hidden, [hidden], [aria-hidden='true']"
_BLOCK_LEVEL_TAGS = frozenset(
    {
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "li",
        "td",
        "th",
        "caption",
        "figcaption",
        "blockquote",
        "dt",
        "dd",
        "button",
    }
)
_SENTENCE_ENDINGS = (".", "!", "?", ":", ";")


def _normalize_text_piece(text: str) -> str:
    # Collapse HTML gaps (newlines, tags) into a single space.
    text = re.sub(r"\s+", " ", text)
    # Tags around punctuation (e.g. </b>.) become "word ." with get_text(" ").
    return re.sub(r"\s+([.,;:!?])", r"\1", text).strip()


def _join_text_parts(parts) -> str:
    filtered = [part.strip() for part in parts if part and str(part).strip()]
    if not filtered:
        return ""
    result = filtered[0].rstrip()
    for part in filtered[1:]:
        if result.endswith(_SENTENCE_ENDINGS):
            result = f"{result} {part}"
        else:
            result = f"{result}. {part}"
    return result


def _collect_block_texts(node, parts: list[str]) -> None:
    # Split rendered HTML into leaf block-level pieces (heading, paragraph, …)
    # so they can be joined with ". " later. Nested blocks (e.g. p inside td)
    # are recursed so each leaf is collected once. Standalone <a> (DSFR buttons)
    # are treated as their own piece; inline links inside a <p> are not.
    name = getattr(node, "name", None)
    if not name:
        return
    if name in _BLOCK_LEVEL_TAGS:
        if node.find(_BLOCK_LEVEL_TAGS):
            for child in node.children:
                _collect_block_texts(child, parts)
        else:
            text = _normalize_text_piece(node.get_text(" "))
            if text:
                parts.append(text)
        return
    if name == "a" and not node.find_parent(_BLOCK_LEVEL_TAGS):
        text = _normalize_text_piece(node.get_text(" "))
        if text:
            parts.append(text)
        return
    for child in getattr(node, "children", []):
        _collect_block_texts(child, parts)


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for el in soup(["script", "style"]):
        el.decompose()
    for el in soup.select(_HIDDEN_CONTENT_SELECTOR):
        el.decompose()
    parts: list[str] = []
    _collect_block_texts(soup, parts)
    if parts:
        return _join_text_parts(parts)
    return _normalize_text_piece(soup.get_text(" "))


def _render_context(page=None) -> dict:
    request = HttpRequest()
    request.method = "GET"
    request.META["SERVER_NAME"] = "localhost"
    request.META["SERVER_PORT"] = "80"
    context = {"request": request}
    if page is not None:
        context["page"] = page
    return context


def _block_template(inner) -> bool:
    return bool(getattr(getattr(inner, "meta", None), "template", None))


def _join_block_texts(children, page=None) -> str:
    return _join_text_parts(get_streamblock_raw_text(child, page=page) for child in children)


def _extract_stored_text(inner, value, page=None) -> str:
    if isinstance(inner, RichTextBlock):
        html = value.source if hasattr(value, "source") else str(value)
        return _html_to_text(html)

    if isinstance(inner, MarkdownBlock):
        return _html_to_text(str(value))

    if isinstance(inner, (CharBlock, TextBlock)):
        return str(value).strip()

    if isinstance(inner, StructBlock):
        bound_blocks = getattr(value, "bound_blocks", None)
        if not bound_blocks:
            return ""
        return _join_block_texts(bound_blocks.values(), page=page)

    if isinstance(inner, ListBlock):
        # ListValue iterates raw child values, not BoundBlocks.
        children = getattr(value, "bound_blocks", None)
        if children is None:
            return ""
        return _join_block_texts(children, page=page)

    if isinstance(inner, StreamBlock):
        return _join_block_texts(value, page=page)

    return ""


def _try_render_template(block, page=None) -> str | None:
    """Return visible text from the block template, or None if rendering failed."""
    try:
        context = _render_context(page)
        # Several project templates read `block.value` (as in {% include_block %})
        # rather than Wagtail's usual `value`.
        context["block"] = block
        html = block.render(context)
    except Exception:
        logger.exception(
            "Could not render block %r for search description, falling back to stored values",
            getattr(getattr(block, "block", None), "name", type(block).__name__),
        )
        return None
    return _html_to_text(html)


def get_streamblock_raw_text(block, page=None) -> str:
    """
    Get the visible text of a streamblock.

    Blocks with templates are rendered so computed labels (tables, contact
    snippets, link text, …) are included. Template-less structs are recursed
    instead of using Wagtail's render_basic, which would leak layout fields
    such as column width.
    """
    try:
        inner = getattr(block, "block", None)
        if inner is None or inner.name in REMOVABLE_BLOCK_NAMES:
            return ""

        value = block.value
        if value is None or value == "":
            return ""

        if _block_template(inner) and inner.name not in DO_NOT_RENDER_TEMPLATES:
            rendered = _try_render_template(block, page=page)
            if rendered is not None:
                return rendered

        return _extract_stored_text(inner, value, page=page)
    except Exception:
        logger.exception(
            "Could not extract search description text from block %r",
            getattr(getattr(block, "block", None), "name", type(block).__name__),
        )
        return ""


def get_search_description(*streamfields, max_chars: int | None = None, page=None) -> str:
    """
    Get the visible text of one or more streamfields. Used to pre-fill the search description field.
    """
    raw_text = _join_block_texts(
        (block for streamfield in streamfields if streamfield for block in streamfield),
        page=page,
    )
    if not raw_text:
        return ""

    # Truncate at the last space before the max_chars limit.
    if max_chars and len(raw_text) > max_chars:
        truncated = raw_text[:max_chars]
        cut = truncated.rfind(" ")
        if cut > 0:
            truncated = truncated[:cut]
        raw_text = f"{truncated.rstrip()} [...]"

    return raw_text
