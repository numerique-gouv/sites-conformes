from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"  # type: ignore
    name = "sites_conformes.dashboard"
    label = "sites_conformes_dashboard"
