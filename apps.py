from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SitesConformesAppConfig(AppConfig):
    name = "sites_conformes"
    label = "sites_conformes"
    verbose_name = _("Sites Conformes")
    default_auto_field = "django.db.models.AutoField"
