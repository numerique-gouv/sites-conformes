from django.core.exceptions import ValidationError
from django.db import models
from django.template.defaultfilters import slugify
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel, TitleFieldPanel
from wagtail.admin.widgets.slug import SlugInput
from wagtail.api import APIField
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Orderable
from wagtail.models.i18n import TranslatableMixin
from wagtail.search import index

from sites_conformes.blog.blocks import COLOPHON_BLOCKS
from sites_conformes.core.constants import LIMITED_RICHTEXTFIELD_FEATURES


class AbstractTaxonomy(TranslatableMixin, index.Indexed, Orderable):
    """
    Base model for hierarchical publication taxonomies (Collection, Theme, …).

    Subclasses only need to set Meta.verbose_name / verbose_name_plural.
    """

    name = models.CharField(max_length=80, unique=True, verbose_name=_("Name"))
    slug = models.SlugField(unique=True, max_length=80)
    parent = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        related_name="children",
        verbose_name=_("Parent"),
        on_delete=models.SET_NULL,
    )
    description = RichTextField(
        max_length=500,
        features=LIMITED_RICHTEXTFIELD_FEATURES,
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Displayed at the top of the taxonomy listing page"),
    )  # type: ignore
    colophon = StreamField(
        COLOPHON_BLOCKS,
        blank=True,
        use_json_field=True,
        help_text=_("Text displayed at the end of every page in the taxonomy"),
    )

    panels = [
        TitleFieldPanel("name"),
        FieldPanel("slug", widget=SlugInput),
        FieldPanel("description"),
        FieldPanel("colophon"),
        FieldPanel("parent"),
    ]

    api_fields = [
        APIField("name"),
        APIField("slug"),
        APIField("description"),
        APIField("colophon"),
        APIField("parent"),
    ]

    search_fields = [index.SearchField("name")]

    class Meta:
        abstract = True
        ordering = ["name"]
        unique_together = [
            ("translation_key", "locale"),
            ("name", "locale"),
            ("slug", "locale"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.parent:
            parent = self.parent
            if self.parent == self:
                raise ValidationError(_("Parent %(type)s cannot be self.") % {"type": self._meta.verbose_name.lower()})
            if parent.parent and parent.parent == self:
                raise ValidationError(_("Cannot have circular Parents."))

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)
