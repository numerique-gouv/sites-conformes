from django.apps import AppConfig


class ContentManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sites_conformes.core"
    label = "sites_conformes_core"

    def ready(self):
        from sites_conformes.core import checks  # noqa: F401
