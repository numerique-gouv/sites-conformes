from django.db import models
from modelcluster.fields import ParentalKey
from modelcluster.tags import ClusterTaggableManager
from taggit.models import TaggedItemBase

from sites_conformes.core.abstract import AbstractContentPage


class CustomContentPage(AbstractContentPage):
    """
    Reference implementation of a custom content page model, used by the
    test suite to exercise the SF_CONTENTPAGE_MODEL setting.
    """

    template = "sites_conformes_core/content_page.html"

    tags = ClusterTaggableManager(through="TagCustomContentPage", blank=True)

    subtitle = models.CharField(max_length=255, blank=True, default="")


class TagCustomContentPage(TaggedItemBase):
    content_object = ParentalKey("CustomContentPage", related_name="customcontentpage_tags")  # type: ignore
