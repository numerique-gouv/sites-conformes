from django.apps import AppConfig


class ProconnectConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"  # type: ignore
    name = "sites_conformes.proconnect"
    label = "sites_conformes_proconnect"
