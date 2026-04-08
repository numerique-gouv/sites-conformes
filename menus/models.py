# myapp/models.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel, HelpPanel
from wagtail.fields import StreamField
from wagtail.models import Site, TranslatableMixin

from menus.blocks import FOOTER_BOTTOM_MENU_BLOCKS, MAIN_MENU_BLOCKS, TOP_MENU_BLOCKS


class TopMenu(TranslatableMixin, models.Model):
    """
    The menu in the top right corner of a site.
    """

    site = models.OneToOneField(
        Site,
        on_delete=models.CASCADE,
        verbose_name=_("Site"),
        default=1,
    )

    items = StreamField(
        TOP_MENU_BLOCKS,
        max_num=3,
        use_json_field=True,
        verbose_name=_("Menu items"),
        blank=True,
    )
    help_panel_content = [
        _("The top menu of the website, displayed in the top right corner."),
        _("There can only be one top menu per site."),
        _("It can contain up to three links."),
    ]
    panels = [
        HelpPanel(content="".join(f"<p>{s}</p>" for s in help_panel_content)),
        FieldPanel("site"),
        FieldPanel("items"),
    ]

    class Meta(TranslatableMixin.Meta):
        verbose_name = _("Top menu")
        verbose_name_plural = _("Top menus")

    def __str__(self):
        return _("Top menu for site {hostname}").format(hostname=self.site.hostname)


class FooterBottomMenu(TranslatableMixin, models.Model):
    """
    The menu at the bottom part of the footer of a site.
    This menu contains the legal links: Terms of Service, Privacy Policy, etc.
    """

    site = models.OneToOneField(
        Site,
        on_delete=models.CASCADE,
        verbose_name=_("Site"),
        default=1,
    )

    items = StreamField(
        FOOTER_BOTTOM_MENU_BLOCKS,
        use_json_field=True,
        verbose_name=_("Menu items"),
        blank=True,
    )

    help_panel_content = [
        _("The footer bottom menu of the website, displayed at the bottom of the footer."),
        _("There can only be one footer bottom menu per site."),
        _("This menu contains the legal links: Terms of Service, Privacy Policy, etc."),
    ]
    panels = [
        HelpPanel(content="".join(f"<p>{s}</p>" for s in help_panel_content)),
        FieldPanel("site"),
        FieldPanel("items"),
    ]

    class Meta(TranslatableMixin.Meta):
        verbose_name = _("Footer bottom menu")
        verbose_name_plural = _("Footer bottom menus")

    def __str__(self):
        return _("Footer bottom menu for site {hostname}").format(hostname=self.site.hostname)


class MainMenu(TranslatableMixin, models.Model):
    """
    The main menu of a site.
    """

    site = models.OneToOneField(
        Site,
        on_delete=models.CASCADE,
        verbose_name=_("Site"),
        default=1,
    )

    items = StreamField(
        MAIN_MENU_BLOCKS,
        use_json_field=True,
        verbose_name=_("Menu items"),
        blank=True,
        help_text=_("The recommended maximum number of items in the main menu is 8."),
    )

    help_panel_content = [
        _("The main menu of the website, displayed in the main navigation area."),
        _("There can only be one main menu per site."),
        _("It can contain links, submenus, and mega menus."),
        _("It is recommended to avoid mixing submenus and mega menus."),
    ]
    panels = [
        HelpPanel(content="".join(f"<p>{s}</p>" for s in help_panel_content)),
        FieldPanel("site"),
        FieldPanel("items"),
    ]

    class Meta(TranslatableMixin.Meta):
        verbose_name = _("Main menu")
        verbose_name_plural = _("Main menus")

    def __str__(self):
        return _("Main menu for site {hostname}").format(hostname=self.site.hostname)
