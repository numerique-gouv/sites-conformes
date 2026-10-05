from django.db import models
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from modelcluster.tags import ClusterTaggableManager
from taggit.models import TaggedItemBase
from wagtail.admin.panels import FieldPanel

from sites_conformes.blog.models import AbstractBlogEntryPage, AbstractBlogIndexPage
from sites_conformes.core.models import AbstractCatalogIndexPage, AbstractContentPage
from sites_conformes.events.models import AbstractEventEntryPage, AbstractEventsIndexPage
from sites_conformes.forms.models import AbstractFormField, AbstractFormPage


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


class CustomCatalogIndexPage(AbstractCatalogIndexPage):
    pass


class CustomBlogIndexPage(AbstractBlogIndexPage):
    pass


class CustomBlogEntryPage(AbstractBlogEntryPage):
    """
    Reference implementation of a custom blog entry model: the tags, the categories
    and their through models are declared on the concrete model.
    """

    tags = ClusterTaggableManager(through="TagCustomBlogEntryPage", blank=True)
    blog_categories = ParentalManyToManyField(
        "sites_conformes_blog.Category",
        through="CategoryCustomBlogEntryPage",
        blank=True,
        verbose_name=_("Categories"),
    )
    subtitle = models.CharField(max_length=255, blank=True, default="")


class TagCustomBlogEntryPage(TaggedItemBase):
    content_object = ParentalKey("CustomBlogEntryPage", related_name="tagged_items")


class CategoryCustomBlogEntryPage(models.Model):
    category = models.ForeignKey("sites_conformes_blog.Category", related_name="+", on_delete=models.CASCADE)
    page = ParentalKey("CustomBlogEntryPage", related_name="entry_categories")


class CustomEventsIndexPage(AbstractEventsIndexPage):
    pass


class CustomEventEntryPage(AbstractEventEntryPage):
    tags = ClusterTaggableManager(through="TagCustomEventEntryPage", blank=True)
    event_categories = ParentalManyToManyField(
        "sites_conformes_blog.Category",
        through="CategoryCustomEventEntryPage",
        blank=True,
        verbose_name=_("Categories"),
    )


class TagCustomEventEntryPage(TaggedItemBase):
    content_object = ParentalKey("CustomEventEntryPage", related_name="tagged_items")


class CategoryCustomEventEntryPage(models.Model):
    category = models.ForeignKey("sites_conformes_blog.Category", related_name="+", on_delete=models.CASCADE)
    page = ParentalKey("CustomEventEntryPage", related_name="entry_categories")


class CustomFormPage(AbstractFormPage):
    pass


class CustomFormField(AbstractFormField):
    # ``form_fields`` is the name Wagtail and the shipped templates expect
    page = ParentalKey("CustomFormPage", on_delete=models.CASCADE, related_name="form_fields")
