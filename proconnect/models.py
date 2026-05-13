from django.contrib.auth import get_user_model
from django.core.validators import validate_domain_name
from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel
from wagtail.search import index

from sites_conformes.proconnect.validators import sub_validator

User = get_user_model()


class UserOIDC(models.Model):
    # Join the user with the OIDC claims without affecting the user model
    user = models.OneToOneField(User, on_delete=models.CASCADE, unique=True)

    sub = models.CharField(
        _("sub"),
        help_text=_("Required. 255 characters or fewer. Letters, numbers, and @/./+/-/_/: characters only."),
        max_length=255,
        unique=True,
        validators=[sub_validator],
        blank=True,
        null=True,
    )

    siret = models.CharField(
        _("SIRET"),
        max_length=14,
        blank=True,
    )

    def __str__(self):
        return self.user.get_username()


class WhitelistedEmailDomain(index.Indexed, models.Model):
    """
    Used for the domain whitelist validation
    """

    domain = models.CharField(
        _("domain name"),
        help_text=_("Required. 255 characters or fewer. Needs to be a valid domain name."),
        max_length=255,
        unique=True,
        validators=[validate_domain_name],
    )

    def __str__(self):
        return self.domain

    panels = [
        FieldPanel("domain"),
    ]

    search_fields = [
        index.SearchField("domain"),
        index.AutocompleteField("domain"),
    ]

    class Meta:
        ordering = ["domain"]
        verbose_name = _("whitelisted email domain")
        verbose_name_plural = _("whitelisted email domains")
