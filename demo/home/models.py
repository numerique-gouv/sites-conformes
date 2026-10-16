from django.db import models
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from modelcluster.tags import ClusterTaggableManager
from taggit.models import TaggedItemBase
from wagtail.admin.panels import FieldPanel
from wagtail.models import Page

from sites_conformes.blog.models import AbstractBlogEntryPage
from sites_conformes.core.models import AbstractContentPage, Category


class HomePage(Page):
    pass


class CustomContentPage(AbstractContentPage):
    """
    Replaces the shipped ContentPage (setting SF_CONTENTPAGE_MODEL),
    see docs/paquet/modele-de-page-personnalise.md.
    """

    tags = ClusterTaggableManager(through="TagCustomContentPage", blank=True)
    subtitle = models.CharField(max_length=255, blank=True, default="")

    content_panels = AbstractContentPage.content_panels + [
        FieldPanel("tags"),
        FieldPanel("subtitle"),
    ]


class TagCustomContentPage(TaggedItemBase):
    content_object = ParentalKey("CustomContentPage", related_name="tagged_items")


class CustomBlogEntryPage(AbstractBlogEntryPage):
    """
    Replaces the shipped BlogEntryPage (setting SF_BLOGENTRYPAGE_MODEL),
    see docs/paquet/modele-de-page-personnalise.md.
    """

    tags = ClusterTaggableManager(through="TagCustomBlogEntryPage", blank=True)
    categories = ParentalManyToManyField(Category, through="CategoryCustomBlogEntryPage", blank=True)


class TagCustomBlogEntryPage(TaggedItemBase):
    content_object = ParentalKey("CustomBlogEntryPage", related_name="tagged_items")


class CategoryCustomBlogEntryPage(models.Model):
    category = models.ForeignKey(Category, related_name="+", on_delete=models.CASCADE)
    page = ParentalKey("CustomBlogEntryPage", related_name="entry_categories")
