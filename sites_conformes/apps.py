from django.apps import AppConfig


class SitesConformesAppConfig(AppConfig):
    name = "sites_conformes"
    label = "sites_conformes"
    # Brand name — kept untranslated so makemessages doesn't churn locale files.
    verbose_name = "Sites Conformes"
    default_auto_field = "django.db.models.AutoField"
