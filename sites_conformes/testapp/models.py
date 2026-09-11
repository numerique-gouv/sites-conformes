from django.db import models
from modelcluster.fields import ParentalKey
from modelcluster.tags import ClusterTaggableManager
from taggit.models import TaggedItemBase
from wagtail.admin.panels import FieldPanel

from sites_conformes.core.models import AbstractContentPage


class CustomContentPage(AbstractContentPage):
    """
    Reference implementation of a custom content page model.
    """

    tags = ClusterTaggableManager(through="TagCustomContentPage", blank=True)
    subtitle = models.CharField(max_length=255, blank=True, default="")

    content_panels = AbstractContentPage.content_panels + [
        FieldPanel("tags"),
        FieldPanel("subtitle"),
    ]


class TagCustomContentPage(TaggedItemBase):
    content_object = ParentalKey("CustomContentPage", related_name="tagged_items")
