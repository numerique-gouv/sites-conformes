from django.core.paginator import Paginator
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.forms.widgets import Textarea, mark_safe
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from dsfr.constants import NOTICE_TYPE_CHOICES
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from modelcluster.tags import ClusterTaggableManager
from taggit.models import Tag as TaggitTag, TaggedItemBase
from unidecode import unidecode
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel, ObjectList, TabbedInterface
from wagtail.api import APIField
from wagtail.contrib.routable_page.models import RoutablePageMixin, path
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import RichTextField
from wagtail.images import get_image_model_string
from wagtail.models import Orderable
from wagtail.snippets.models import register_snippet

from content_manager.abstract import SitesFacilesBasePage
from content_manager.constants import LIMITED_RICHTEXTFIELD_FEATURES
from content_manager.managers import TagManager
from content_manager.widgets import DsfrIconPickerWidget


class ContentPage(SitesFacilesBasePage):
    tags = ClusterTaggableManager(through="TagContentPage", blank=True)

    class Meta:
        verbose_name = _("Content page")

    content_panels = SitesFacilesBasePage.content_panels + [
        FieldPanel("tags"),
    ]

    api_fields = SitesFacilesBasePage.api_fields + [
        APIField("tags"),
    ]


class TagContentPage(TaggedItemBase):
    content_object = ParentalKey("ContentPage", related_name="contentpage_tags")


class CatalogIndexPage(RoutablePageMixin, SitesFacilesBasePage):
    entries_per_page = models.PositiveSmallIntegerField(
        default=10,
        validators=[MaxValueValidator(100), MinValueValidator(1)],
        verbose_name=_("Entries per page"),
    )

    # Filters
    filter_by_tag = models.BooleanField(_("Filter by tag"), default=True)

    settings_panels = SitesFacilesBasePage.settings_panels + [
        FieldPanel("entries_per_page"),
        MultiFieldPanel(
            [
                FieldPanel("filter_by_tag"),
            ],
            heading=_("Show filters"),
        ),
    ]

    subpage_types = ["content_manager.ContentPage"]

    class Meta:
        verbose_name = _("Catalog index page")

    @property
    def entries(self):
        # Get a list of live content pages that are children of this page
        return ContentPage.objects.child_of(self).live().specific().prefetch_related("tags")

    def get_context(self, request, *args, **kwargs):
        context = super(CatalogIndexPage, self).get_context(request, *args, **kwargs)
        entries = self.entries

        extra_breadcrumbs = None
        extra_title = ""

        tag = request.GET.get("tag")
        if tag:
            tag = get_object_or_404(Tag, slug=tag)
            entries = entries.filter(tags=tag)
            extra_breadcrumbs = {
                "links": [
                    {"url": self.get_url(), "title": self.title},
                    {
                        "url": f"{self.get_url()}{self.reverse_subpage('tags_list')}",
                        "title": _("Tags"),
                    },
                ],
                "current": tag,
            }
            extra_title = _("Pages tagged with %(tag)s") % {"tag": tag}

        # Pagination
        page_number = request.GET.get("page")
        page_size = self.entries_per_page

        paginator = Paginator(entries, page_size)  # Show <page_size> entries per page
        entries = paginator.get_page(page_number)

        context["entries"] = entries
        context["current_tag"] = tag
        context["paginator"] = paginator
        context["extra_title"] = extra_title

        # Filters
        context["tags"] = self.get_tags()

        if extra_breadcrumbs:
            context["extra_breadcrumbs"] = extra_breadcrumbs

        return context

    def get_tags(self) -> models.QuerySet:
        ids = self.entries.values_list("tags", flat=True)
        return Tag.objects.tags_with_usecount(1).filter(id__in=ids).order_by("name")

    @property
    def show_filters(self) -> bool | models.BooleanField:
        return self.filter_by_tag and self.get_tags().count() > 0

    @path("tags/", name="tags_list")
    def tags_list(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        extra_title = _("Tags")
        tags = self.get_tags()

        tags_by_first_letter = {}
        for tag in tags:
            first_letter = unidecode(tag.slug[0].upper())
            if first_letter not in tags_by_first_letter:
                tags_by_first_letter[first_letter] = []
            tags_by_first_letter[first_letter].append(tag)

        extra_breadcrumbs = {
            "links": [
                {"url": self.get_url(), "title": self.title},
            ],
            "current": _("Tags"),
        }

        return self.render(
            request,
            context_overrides={
                "title": _("Tags"),
                "sorted_tags": tags_by_first_letter,
                "page": self,
                "extra_title": extra_title,
                "extra_breadcrumbs": extra_breadcrumbs,
            },
            template="content_manager/tags_list_page.html",
        )


@register_snippet
class Tag(TaggitTag):
    objects = TagManager()

    class Meta:
        proxy = True
        verbose_name = _("Tag")


class MonospaceField(models.TextField):
    """
    A TextField which renders as a large HTML textarea with monospace font.
    """

    def formfield(self, **kwargs):
        kwargs["widget"] = Textarea(
            attrs={
                "rows": 12,
                "class": "monospace",
                "spellcheck": "false",
            }
        )
        return super().formfield(**kwargs)


@register_setting(icon="code")
class CustomScriptsSettings(BaseSiteSetting):
    class Meta:
        verbose_name = _("Custom scripts")

    head_scripts = MonospaceField(
        blank=True,
        null=True,
        verbose_name=_("Scripts in the <head> section"),
        help_text=_("Allows for scripts to be placed in the <head> tag of the website pages."),
    )

    body_scripts = MonospaceField(
        blank=True,
        null=True,
        verbose_name=_("Scripts in the <body> section"),
        help_text=_("Allows for scripts to be placed at the end of the <body> tag of the website pages."),
    )

    use_tarteaucitron = models.BooleanField(
        _("Use Tarteaucitron?"),
        default=False,
        help_text=mark_safe(
            _(
                'See <a href="https://sites-faciles.beta.numerique.gouv.fr/documentation/gestion-des-cookies/">Documentation</a>'
            )
        ),
    )

    panels = [
        MultiFieldPanel(
            [
                FieldPanel(
                    "use_tarteaucitron",
                ),
                FieldPanel("head_scripts"),
                FieldPanel("body_scripts"),
            ],
            heading=_("Custom scripts"),
            help_text=_("Allows to add custom CSS and JS to the site, for example for Matomo, Tarteaucitron…"),
        ),
    ]


@register_setting(icon="cog")
class CmsDsfrConfig(ClusterableModel, BaseSiteSetting):
    class Meta:
        verbose_name = _("Site configuration")
        verbose_name_plural = _("Site configurations")

    header_brand = models.CharField(
        _("Institution (header)"),
        max_length=200,
        default="Intitulé officiel",
        help_text=mark_safe(
            _(
                'Institution brand as defined on <a href="https://www.info.gouv.fr/marque-de-letat/le-bloc-marque">official page</a>.'  # noqa
            )
        ),
        blank=True,
    )
    header_brand_html = models.CharField(
        _("Institution with line break (header)"),
        max_length=200,
        default="Intitulé<br />officiel",
        blank=True,
        help_text=_("Institution brand with <br /> tags for line breaks"),
    )
    footer_brand = models.CharField(
        _("Institution (footer)"),
        max_length=200,
        default="Intitulé officiel",
        blank=True,
    )

    footer_brand_html = models.CharField(
        _("Institution with line break (footer)"),
        max_length=200,
        default="Intitulé<br />officiel",
        blank=True,
    )

    site_title = models.CharField(
        _("Site title"),
        max_length=200,
        default=_("Site title"),
        blank=True,
    )
    site_tagline = models.CharField(
        _("Site tagline"),
        max_length=200,
        default=_("Site tagline"),
        blank=True,
    )

    notice_title = RichTextField(
        _("Notice title"),
        default="",
        blank=True,
        features=LIMITED_RICHTEXTFIELD_FEATURES,
        help_text=_("Can include HTML"),
    )

    notice_description = RichTextField(
        _("Notice description"),
        default="",
        blank=True,
        help_text=_("Can include HTML"),
    )
    notice_type = models.CharField(
        _("Notice type"),
        choices=NOTICE_TYPE_CHOICES,
        default="info",
        blank=True,
        max_length=20,
        help_text=mark_safe(
            _(
                'Use is strictly regulated, see \
            <a href="https://www.systeme-de-design.gouv.fr/composants-et-modeles/composants/bandeau-d-information-importante/">documentation</a>.'
            )
        ),
    )

    notice_link = models.URLField(
        _("Notice link"),
        help_text=_("Standardized consultation link at the end of the notice. Max length: 2000 characters."),
        max_length=2000,
        default="",
        blank=True,
    )

    notice_icon_class = models.CharField(
        _("Notice icon class"),
        max_length=200,
        default="",
        blank=True,
        help_text=_("For weather alerts only"),
    )

    notice_is_collapsible = models.BooleanField(_("Collapsible?"), default=False)  # type: ignore

    beta_tag = models.BooleanField(_("Show the BETA tag next to the title"), default=False)

    header_login_button = models.BooleanField(_("Show a login button in the header"), default=False)

    footer_description = RichTextField(
        _("Description"),
        default="",
        blank=True,
        features=LIMITED_RICHTEXTFIELD_FEATURES,
    )

    # Operator logo
    operator_logo_file = models.ForeignKey(
        get_image_model_string(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("Site logo"),
    )

    operator_logo_display = models.CharField(
        _("Logo display"),
        choices=[("header-footer", _("Header and Footer")), ("header-only", _("Header only"))],
        default="header-footer",
        blank=True,
        max_length=20,
    )

    operator_logo_alt = models.CharField(
        _("Logo alt text"),
        max_length=200,
        blank=True,
        help_text=_("Must contain the text present in the image."),
    )
    operator_logo_width = models.DecimalField(
        _("Width (em)"),
        max_digits=3,
        decimal_places=1,
        null=True,
        default="5.0",
        help_text=_(
            "To be adjusted according to the width of the logo.\
            Example for a vertical logo: 3.5, Example for a horizontal logo: 8."
        ),
    )

    search_bar = models.BooleanField(_("Display search bar in the header"), default=False)  # type: ignore
    theme_modale_button = models.BooleanField(_("Display theme modale button"), default=False)  # type: ignore
    mourning = models.BooleanField(_("Mourning"), default=False)  # type: ignore

    newsletter_description = models.TextField(_("Newsletter description"), default="", blank=True)

    newsletter_url = models.URLField(
        _("Newsletter registration URL"),
        help_text=_("Max length: 2000 characters."),
        max_length=2000,
        default="",
        blank=True,
    )

    share_links_content_pages = models.BooleanField(_("Activate share links on content_pages"), default=False)
    share_links_blog_posts = models.BooleanField(_("Activate share links on blog posts"), default=False)
    share_links_events = models.BooleanField(_("Activate share links on event pages"), default=False)

    share_links_facebook = models.BooleanField(
        _("Display a Share on Facebook link at the bottom of pages"), default=False
    )
    share_links_twitter = models.BooleanField(
        _("Display a Share on X (previously Twitter) link at the bottom of pages"), default=False
    )
    share_links_linkedin = models.BooleanField(
        _("Display a Share on LinkedIn link at the bottom of pages"), default=False
    )
    share_links_email = models.BooleanField(_("Display a Share via email link at the bottom of pages"), default=True)
    share_links_clipboard = models.BooleanField(
        _("Display a Copy to clipboard link at the bottom of pages"), default=True
    )

    site_panels = [
        FieldPanel("site_title"),
        FieldPanel("site_tagline"),
        FieldPanel("footer_description"),
        MultiFieldPanel(
            [
                FieldPanel("notice_title"),
                FieldPanel("notice_description"),
                FieldPanel("notice_type"),
                FieldPanel("notice_link"),
                FieldPanel("notice_icon_class", widget=DsfrIconPickerWidget),
                FieldPanel("notice_is_collapsible"),
            ],
            heading=_("Important notice"),
            help_text=_(
                "The important notice banner should only be used for essential and temporary information. \
                (Excessive or continuous use risks “drowning” the message.)"
            ),
        ),
        MultiFieldPanel(
            [
                FieldPanel("operator_logo_file"),
                FieldPanel("operator_logo_display"),
                FieldPanel("operator_logo_alt"),
                FieldPanel("operator_logo_width"),
            ],
            heading=_("Site logo"),
        ),
        MultiFieldPanel(
            [
                FieldPanel("search_bar"),
                FieldPanel("mourning"),
                FieldPanel("beta_tag"),
                FieldPanel("theme_modale_button"),
                FieldPanel("header_login_button"),
            ],
            heading=_("Advanced settings"),
        ),
    ]

    brand_panels = [
        MultiFieldPanel(
            [
                FieldPanel("header_brand"),
                FieldPanel("header_brand_html"),
            ],
            heading=_("Header"),
        ),
        MultiFieldPanel(
            [
                FieldPanel("footer_brand"),
                FieldPanel("footer_brand_html"),
            ],
            heading=_("Footer"),
        ),
    ]

    newsletter_social_media_panels = [
        MultiFieldPanel(
            [
                FieldPanel("newsletter_description"),
                FieldPanel("newsletter_url"),
            ],
            heading=_("Newsletter"),
        ),
        InlinePanel("social_media_items", label=_("Social media items")),
        MultiFieldPanel(
            [
                FieldPanel("share_links_content_pages"),
                FieldPanel("share_links_blog_posts"),
                FieldPanel("share_links_events"),
            ],
            heading=_("Activate share links by type of page"),
        ),
        MultiFieldPanel(
            [
                FieldPanel("share_links_facebook"),
                FieldPanel("share_links_twitter"),
                FieldPanel("share_links_linkedin"),
                FieldPanel("share_links_email"),
                FieldPanel("share_links_clipboard"),
            ],
            heading=_("Types of share links"),
        ),
    ]
    edit_handler = TabbedInterface(
        [
            ObjectList(site_panels, heading=_("Generic")),
            ObjectList(brand_panels, heading=_("Brand block")),
            ObjectList(newsletter_social_media_panels, heading=_("Newsletter, social media and share links")),
        ]
    )

    def show_newsletter_block(self):
        if self.newsletter_description and self.newsletter_url:
            return True
        else:
            return False

    def show_social_block(self):
        return bool(self.social_media_items.count())

    def show_newsletter_and_social_block(self):
        # Returns true if at least one of the two blocks is used
        if self.show_newsletter_block() or self.show_social_block():
            return True
        else:
            return False

    def show_share_links(self):
        return (
            self.share_links_facebook
            or self.share_links_twitter
            or self.share_links_linkedin
            or self.share_links_email
            or self.share_links_clipboard
        )


class SocialMediaItem(Orderable):
    site_config = ParentalKey(CmsDsfrConfig, related_name="social_media_items")
    title = models.CharField(_("Title"), max_length=200, default="", blank=True)

    url = models.URLField(
        _("URL"),
        help_text=_("Max length: 2000 characters."),
        max_length=2000,
        default="",
        blank=True,
    )
    icon_class = models.CharField(_("Icon class"), max_length=200, default="", blank=True)

    panels = [
        FieldPanel("title"),
        FieldPanel("url"),
        FieldPanel("icon_class", widget=DsfrIconPickerWidget),
    ]

    class Meta:
        verbose_name = _("Social media item")
        verbose_name_plural = _("Social media items")


# Mega-Menus
class MegaMenuCategory(Orderable):
    mega_menu = ParentalKey("content_manager.MegaMenu", related_name="categories", on_delete=models.CASCADE)
    category = models.ForeignKey("wagtailmenus.FlatMenu", on_delete=models.CASCADE, verbose_name=_("Category"))

    class Meta:
        verbose_name = _("Mega menu category")
        verbose_name_plural = _("Mega menu categories")


@register_snippet
class MegaMenu(ClusterableModel):
    name = models.CharField(_("Name"), max_length=255)
    parent_menu_item = models.ForeignKey(
        "wagtailmenus.MainMenuItem", on_delete=models.CASCADE, related_name="megamenu_parent_menu_items"
    )
    description = models.TextField(_("Description"), blank=True)
    main_link = models.URLField(
        _("Main link"), help_text=_("Max length: 2000 characters."), max_length=2000, blank=True, null=True
    )

    panels = [
        FieldPanel("name"),
        FieldPanel("parent_menu_item"),
        FieldPanel("description"),
        FieldPanel("main_link"),
        InlinePanel(
            "categories",
            max_num=4,
            heading=_("Categories"),
            help_text=_("Maximum 4 categories, each with maximum 8 links."),
        ),
    ]

    def __str__(self):  # type: ignore
        return self.name

    def get_categories(self):
        return self.categories.order_by("sort_order")

    class Meta:
        verbose_name = _("Mega menu")
