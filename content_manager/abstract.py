from django.db import models
from django.utils.translation import gettext_lazy as _
from dsfr.constants import COLOR_CHOICES
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.api import APIField
from wagtail.fields import RichTextField, StreamField
from wagtail.images import get_image_model_string
from wagtail.images.api.fields import ImageRenditionField
from wagtail.models import Page
from wagtail.search import index

from content_manager.blocks import HERO_STREAMFIELD_BLOCKS, STREAMFIELD_COMMON_BLOCKS, ButtonsHorizontalListBlock
from content_manager.utils import get_streamfield_raw_text


class SitesFacilesBasePage(Page):
    """
    This class defines a base page model that will be used
    by all pages in Sites Faciles
    """

    hero = StreamField(HERO_STREAMFIELD_BLOCKS, blank=True, use_json_field=True, max_num=1)

    body = StreamField(
        STREAMFIELD_COMMON_BLOCKS,
        blank=True,
        use_json_field=True,
        collapsed=True,
    )
    header_with_title = models.BooleanField(_("Show title in header image?"), default=False)  # type: ignore

    header_image = models.ForeignKey(
        get_image_model_string(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("Header image"),
    )

    header_color_class = models.CharField(
        _("Background color"),
        choices=COLOR_CHOICES,
        null=True,
        blank=True,
        help_text=_("Uses the French Design System colors"),
    )

    header_large = models.BooleanField(_("Full width"), default=False)  # type: ignore
    header_darken = models.BooleanField(_("Darken background image"), default=False)  # type: ignore

    header_cta_text = RichTextField(
        _("Call to action text"),
        null=True,
        blank=True,
    )

    header_cta_buttons = StreamField(
        [
            (
                "buttons",
                ButtonsHorizontalListBlock(
                    help_text=_(
                        """Please use only one primary button.
                        If you use icons, use them on all buttons and align them on the same side."""
                    ),
                    label=_("Buttons"),
                ),
            ),
        ],
        max_num=1,
        null=True,
        blank=True,
    )

    source_url = models.URLField(
        _("Source URL"),
        help_text=_("For imported pages, to allow updates. Max length: 2000 characters."),
        max_length=2000,
        null=True,
        blank=True,
    )

    preview_image = models.ForeignKey(
        get_image_model_string(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("Preview image"),
        help_text=_("Image displayed as a preview when the page is shared on social media"),
    )

    content_panels = Page.content_panels + [
        FieldPanel("hero", heading=_("Hero")),
        FieldPanel("body", heading=_("Body")),
    ]

    configuration_field_panels = list(Page.promote_panels) + [FieldPanel("preview_image")]

    promote_panels = [
        MultiFieldPanel(configuration_field_panels, _("Common page configuration")),
    ]

    search_fields = Page.search_fields + [
        index.SearchField("body"),
    ]

    # Export fields over the API
    api_fields = [
        APIField("hero"),
        APIField("body"),
        APIField("header_image"),
        APIField("header_image_render", serializer=ImageRenditionField("fill-1200x630", source="header_image")),
        APIField("header_image_thumbnail", serializer=ImageRenditionField("fill-376x211", source="header_image")),
        APIField("header_with_title"),
        APIField("header_color_class"),
        APIField("header_large"),
        APIField("header_darken"),
        APIField("header_cta_text"),
        APIField("header_cta_buttons"),
        APIField("public_child_pages"),
        APIField("preview_image"),
        APIField("preview_image_render", serializer=ImageRenditionField("fill-1200x630", source="preview_image")),
    ]

    @property
    def public_child_pages(self):
        return [
            {
                "id": child.id,
                "slug": child.slug,
                "title": child.title,
                "type": f"{child.content_type.app_label}.{child.content_type.model}",
            }
            for child in self.get_children().live().public()
        ]

    @property
    def get_preview_image(self):
        return self.preview_image or self.header_image

    def get_absolute_url(self):
        return self.url

    def save(self, *args, **kwargs):
        if not self.search_description:
            search_description = get_streamfield_raw_text(self.body, max_words=20)
            if search_description:
                self.search_description = search_description
        return super().save(*args, **kwargs)

    class Meta:
        abstract = True
        verbose_name = _("Base page")
        verbose_name_plural = _("Base pages")
