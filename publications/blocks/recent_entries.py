from django.utils.translation import gettext_lazy as _
from wagtail import blocks
from wagtail.blocks import BooleanBlock
from wagtail.snippets.blocks import SnippetChooserBlock

from sites_conformes.core.constants import HEADING_CHOICES_2_5

PUBLICATION_RECENT_ENTRIES_BLOCK = "publication_recent_entries"


class PublicationRecentEntriesStructValue(blocks.StructValue):
    """Filter and list recent publications for a ``PublicationIndexPage``."""

    def posts(self):
        from publications.models import PublicationPage

        index_page = self.get("index_page")
        if not index_page:
            return PublicationPage.objects.none()

        posts = index_page.posts

        collection_filter = self.get("collection_filter")
        if collection_filter:
            posts = posts.filter(collections=collection_filter)

        theme_filter = self.get("theme_filter")
        if theme_filter:
            posts = posts.filter(themes=theme_filter)

        tag_filter = self.get("tag_filter")
        if tag_filter:
            posts = posts.filter(tags=tag_filter)

        author_filter = self.get("author_filter")
        if author_filter:
            posts = posts.filter(authors=author_filter)

        source_filter = self.get("source_filter")
        if source_filter:
            posts = posts.filter(authors__organization=source_filter)

        entries_count = self.get("entries_count")
        return posts[:entries_count]

    def current_filters(self) -> dict:
        filters = {}

        collection_filter = self.get("collection_filter")
        if collection_filter:
            filters["collection"] = collection_filter.slug

        theme_filter = self.get("theme_filter")
        if theme_filter:
            filters["theme"] = theme_filter.slug

        tag_filter = self.get("tag_filter")
        if tag_filter:
            filters["tag"] = tag_filter.slug

        author_filter = self.get("author_filter")
        if author_filter:
            filters["author"] = author_filter.id

        source_filter = self.get("source_filter")
        if source_filter:
            filters["source"] = source_filter.slug

        return filters

    def sub_heading_tag(self):
        heading_tag = self.get("heading_tag")
        if heading_tag == "h2":
            return "h3"
        if heading_tag == "h3":
            return "h4"
        if heading_tag == "h4":
            return "h5"
        return "h6"


class PublicationRecentEntriesBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Title"), required=False)
    heading_tag = blocks.ChoiceBlock(
        label=_("Heading level"),
        choices=HEADING_CHOICES_2_5,
        required=False,
        default="h2",
        help_text=_("Adapt to the page layout. Defaults to heading 2."),
    )
    index_page = blocks.PageChooserBlock(
        label=_("Publications"),
        page_type="publications.PublicationIndexPage",
    )
    entries_count = blocks.IntegerBlock(
        label=_("Number of entries"), required=False, min_value=1, max_value=8, default=3
    )
    collection_filter = SnippetChooserBlock(
        "publications.Collection",
        label=_("Filter by collection"),
        required=False,
    )
    theme_filter = SnippetChooserBlock(
        "publications.Theme",
        label=_("Filter by theme"),
        required=False,
    )
    tag_filter = SnippetChooserBlock("sites_conformes_core.Tag", label=_("Filter by tag"), required=False)
    author_filter = SnippetChooserBlock("sites_conformes_blog.Person", label=_("Filter by author"), required=False)
    source_filter = SnippetChooserBlock(
        "sites_conformes_blog.Organization",
        label=_("Filter by source"),
        help_text=_("The source is the organization of the post author"),
        required=False,
    )
    show_filters = BooleanBlock(label=_("Show filters"), default=False, required=False)

    class Meta:
        icon = "placeholder"
        template = "publications/blocks/publication_recent_entries.html"
        value_class = PublicationRecentEntriesStructValue
